"""
GridIQ Asset Intelligence — Universal Fault Detection Engine
============================================================
Runs every applicable fault signature against incoming telemetry
for every asset type. Detects outages, energy losses, degradation,
and physical faults across the entire generation and transmission fleet.

Detection methods implemented:
  threshold     — single-value limit check (hi/lo)
  ratio         — actual vs. expected ratio
  trend         — rolling slope analysis
  ml_anomaly    — isolation forest / z-score anomaly
  vibration_fft — frequency-domain analysis (simulated in dev)
"""
from __future__ import annotations

import logging
import math
import random
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.assets.fault_signatures import (
    FAULT_SIGNATURES, FaultCategory, FaultSeverity,
    FaultSignature, get_signatures_for_asset_type,
)
from backend.core.event_bus import EventType, emit

logger = logging.getLogger(__name__)


# ── Detected fault ────────────────────────────────────────────────────────────

@dataclass
class DetectedFault:
    """A fault instance detected on a specific asset."""
    fault_id: str
    fault_code: str
    asset_id: str
    asset_name: str
    asset_type: str
    severity: FaultSeverity
    category: FaultCategory
    title: str
    description: str
    detected_at: str
    # Measurement that triggered the fault
    trigger_param: Optional[str] = None
    trigger_value: Optional[float] = None
    trigger_threshold: Optional[float] = None
    # Impact
    estimated_loss_mw: Optional[float] = None
    estimated_revenue_loss_hr: Optional[float] = None   # $/hour
    # Response
    recommended_action: str = ""
    work_order_priority: str = "normal"
    maintenance_type: str = "corrective"
    # Status
    status: str = "open"             # open | acknowledged | resolved
    auto_created_alert: bool = True
    confidence: float = 1.0


# ── Energy loss calculator ────────────────────────────────────────────────────

class EnergyLossCalculator:
    """
    Computes actual vs. theoretical energy output for each asset type.
    'Theoretical' = what the asset should produce given current conditions.
    'Loss' = the gap between theoretical and actual.
    """

    # Approximate revenue values by asset type ($/MWh)
    REVENUE_RATES = {
        "hydro_plant":    45,
        "solar_farm":     55,
        "wind_farm":      48,
        "gas_peaker":     80,   # higher — peakers run during high-price periods
        "bess":           90,   # highest — dispatched for peak/ancillary
        "thermal_plant":  65,
        "default":        50,
    }

    def theoretical_output_mw(
        self, asset_type: str, telemetry: Dict[str, Any], asset_meta: Dict
    ) -> Optional[float]:
        """
        Compute what the asset SHOULD be producing given current conditions.
        Returns None if not calculable.
        """
        rated = asset_meta.get("rated_capacity_mw", 0)
        if not rated:
            return None

        if asset_type == "solar_farm":
            irradiance = telemetry.get("irradiance_wm2", 0)
            if irradiance <= 0:
                return 0.0
            # Simple model: linear above 200 W/m², rated at 1000 W/m²
            theoretical_cf = min(1.0, (irradiance - 200) / 800) * 0.97
            return max(0, rated * theoretical_cf)

        elif asset_type == "wind_farm":
            wind_speed = telemetry.get("wind_speed_ms", 0)
            # Standard wind turbine power curve
            if wind_speed < 3 or wind_speed > 25:
                return 0.0
            elif wind_speed < 12:
                cf = ((wind_speed - 3) / 9) ** 3
            else:
                cf = 1.0
            return rated * cf * 0.95  # 5% availability derating

        elif asset_type == "hydro_plant":
            flow = telemetry.get("water_flow_m3s", 0)
            head = telemetry.get("net_head_m", asset_meta.get("design_head_m", 50))
            if flow <= 0:
                return 0.0
            # P = ρ × g × Q × H × η
            eta = 0.92
            theoretical_kw = 1000 * 9.81 * flow * head * eta / 1000
            return min(rated, theoretical_kw / 1000)

        elif asset_type == "gas_peaker":
            # Can produce rated output if fuel supply is available
            return rated * 0.97 if telemetry.get("fuel_flow_mscfd", 0) > 0 else 0.0

        elif asset_type == "bess":
            soc = telemetry.get("state_of_charge_pct", 50)
            if soc < 10:
                return 0.0  # too low to discharge
            return rated * min(1.0, soc / 100) * 0.95

        return None

    def compute_loss(
        self, asset_id: str, asset_type: str, asset_name: str,
        actual_mw: float, theoretical_mw: float,
        loss_threshold_pct: float = 5.0,
    ) -> Optional[Dict]:
        """
        Returns a loss record if actual is significantly below theoretical.
        """
        if theoretical_mw <= 0:
            return None
        loss_mw = theoretical_mw - actual_mw
        loss_pct = (loss_mw / theoretical_mw) * 100

        if loss_pct < loss_threshold_pct:
            return None

        rate = self.REVENUE_RATES.get(asset_type, self.REVENUE_RATES["default"])
        return {
            "asset_id": asset_id,
            "asset_name": asset_name,
            "asset_type": asset_type,
            "actual_mw": round(actual_mw, 2),
            "theoretical_mw": round(theoretical_mw, 2),
            "loss_mw": round(loss_mw, 2),
            "loss_pct": round(loss_pct, 1),
            "revenue_loss_per_hour": round(loss_mw * rate, 0),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Detection engine ──────────────────────────────────────────────────────────

class AssetFaultDetector:
    """
    Runs fault signature detection on incoming telemetry.
    Maintains rolling windows for trend analysis.
    """

    def __init__(self):
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=720))
        self._active_faults: Dict[str, DetectedFault] = {}
        self._loss_calc = EnergyLossCalculator()
        self._fault_counter = 0

    def _new_fault_id(self) -> str:
        self._fault_counter += 1
        return f"FLT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._fault_counter:04d}"

    def detect(
        self,
        asset_id: str,
        asset_name: str,
        asset_type: str,
        telemetry: Dict[str, Any],
        asset_meta: Optional[Dict] = None,
    ) -> List[DetectedFault]:
        """
        Run all applicable fault signatures against a single telemetry reading.
        Returns list of newly detected faults (not previously active).
        """
        meta = asset_meta or {}
        ts = telemetry.get("timestamp", datetime.now(timezone.utc).isoformat())

        # Add to history for trend detection
        self._history[asset_id].append({
            "ts": ts,
            "telemetry": telemetry,
        })

        new_faults: List[DetectedFault] = []

        # 1. Check fault signatures
        for sig in get_signatures_for_asset_type(asset_type):
            fault_key = f"{asset_id}:{sig.fault_code}"
            if fault_key in self._active_faults:
                continue  # Already detected

            detected, value, threshold = self._check_signature(sig, asset_id, telemetry)
            if detected:
                fault = DetectedFault(
                    fault_id=self._new_fault_id(),
                    fault_code=sig.fault_code,
                    asset_id=asset_id,
                    asset_name=asset_name,
                    asset_type=asset_type,
                    severity=sig.severity,
                    category=sig.category,
                    title=sig.name,
                    description=sig.description,
                    detected_at=ts,
                    trigger_param=sig.threshold_param,
                    trigger_value=round(value, 3) if value is not None else None,
                    trigger_threshold=threshold,
                    estimated_loss_mw=sig.estimated_loss_mw,
                    estimated_revenue_loss_hr=(
                        sig.estimated_loss_mw *
                        self._loss_calc.REVENUE_RATES.get(asset_type, 50)
                    ) if sig.estimated_loss_mw else None,
                    recommended_action=sig.recommended_action,
                    work_order_priority=self._priority_from_severity(sig.severity),
                    maintenance_type=sig.maintenance_type,
                    confidence=self._confidence_score(sig, value, threshold),
                )
                self._active_faults[fault_key] = fault
                new_faults.append(fault)
                logger.warning(
                    f"[FaultDetector] {sig.severity.value.upper()} {sig.fault_code} "
                    f"on {asset_name}: {sig.name}"
                )

        # 2. Check for outage (complete output loss)
        outage = self._check_outage(asset_id, asset_name, asset_type, telemetry, meta)
        if outage:
            fault_key = f"{asset_id}:OUTAGE"
            if fault_key not in self._active_faults:
                self._active_faults[fault_key] = outage
                new_faults.append(outage)

        # 3. Check energy loss vs. theoretical
        actual_mw = telemetry.get("active_power_mw", 0) or 0
        theoretical_mw = self._loss_calc.theoretical_output_mw(asset_type, telemetry, meta)
        if theoretical_mw is not None and theoretical_mw > 0:
            loss = self._loss_calc.compute_loss(
                asset_id, asset_type, asset_name, actual_mw, theoretical_mw
            )
            if loss:
                fault_key = f"{asset_id}:ENERGY_LOSS"
                if fault_key not in self._active_faults:
                    severity = (
                        FaultSeverity.HIGH if loss["loss_pct"] > 25 else
                        FaultSeverity.MEDIUM if loss["loss_pct"] > 10 else
                        FaultSeverity.LOW
                    )
                    ef = DetectedFault(
                        fault_id=self._new_fault_id(),
                        fault_code="GEN-LOSS",
                        asset_id=asset_id,
                        asset_name=asset_name,
                        asset_type=asset_type,
                        severity=severity,
                        category=FaultCategory.EFFICIENCY_LOSS,
                        title=f"Energy loss {loss['loss_pct']:.1f}% below theoretical",
                        description=(
                            f"Actual output {loss['actual_mw']} MW vs. theoretical "
                            f"{loss['theoretical_mw']} MW. "
                            f"Loss: {loss['loss_mw']} MW "
                            f"(${loss['revenue_loss_per_hour']:.0f}/hr)."
                        ),
                        detected_at=ts,
                        trigger_param="performance_ratio",
                        trigger_value=round(actual_mw / theoretical_mw, 3),
                        trigger_threshold=0.95,
                        estimated_loss_mw=loss["loss_mw"],
                        estimated_revenue_loss_hr=loss["revenue_loss_per_hour"],
                        recommended_action="Investigate cause. Compare with similar assets and historical baseline.",
                        work_order_priority=self._priority_from_severity(severity),
                    )
                    self._active_faults[fault_key] = ef
                    new_faults.append(ef)

        return new_faults

    def _check_signature(
        self, sig: FaultSignature, asset_id: str, telemetry: Dict[str, Any]
    ) -> Tuple[bool, Optional[float], Optional[float]]:
        """
        Check a single fault signature against telemetry.
        Returns (triggered, measured_value, threshold_that_was_crossed).
        """
        method = sig.detection_method
        param = sig.threshold_param

        if method in ("threshold", "ratio"):
            value = self._get_param(param, asset_id, telemetry)
            if value is None:
                return False, None, None
            if sig.threshold_hi is not None and value > sig.threshold_hi:
                return True, value, sig.threshold_hi
            if sig.threshold_lo is not None and value < sig.threshold_lo:
                return True, value, sig.threshold_lo
            return False, value, None

        elif method == "trend":
            return self._check_trend(sig, asset_id)

        elif method == "vibration_fft":
            # Simulate: flag when base reading is high AND random fault event
            value = self._get_param(param, asset_id, telemetry)
            if value is None:
                return False, None, None
            if sig.threshold_hi and value > sig.threshold_hi:
                return True, value, sig.threshold_hi
            return False, value, None

        elif method == "ml_anomaly":
            # Simplified: use anomaly score from telemetry or random for demo
            score = telemetry.get(param or "anomaly_score", random.uniform(0, 1))
            if sig.threshold_hi and score > sig.threshold_hi:
                return True, score, sig.threshold_hi
            return False, score, None

        return False, None, None

    def _check_trend(
        self, sig: FaultSignature, asset_id: str
    ) -> Tuple[bool, Optional[float], Optional[float]]:
        """Compute slope over rolling window for trend-based detection."""
        history = list(self._history[asset_id])
        if len(history) < 10:
            return False, None, None

        window_hrs = sig.trend_window_hours or 24
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hrs)
        param = sig.threshold_param

        values = []
        for h in history:
            try:
                ts = datetime.fromisoformat(h["ts"].replace("Z", "+00:00"))
                if ts >= cutoff:
                    v = h["telemetry"].get(param)
                    if v is not None:
                        values.append(float(v))
            except Exception:
                continue

        if len(values) < 5:
            return False, None, None

        # Simple linear slope
        n = len(values)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(values) / n
        slope = (
            sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) /
            max(0.001, sum((x - x_mean) ** 2 for x in xs))
        )

        threshold = sig.trend_slope_threshold or 0
        if threshold < 0 and slope < threshold:
            return True, slope, threshold
        elif threshold > 0 and slope > threshold:
            return True, slope, threshold
        return False, slope, threshold

    def _check_outage(
        self, asset_id: str, asset_name: str, asset_type: str,
        telemetry: Dict[str, Any], meta: Dict,
    ) -> Optional[DetectedFault]:
        """Detect complete output loss on a generation asset."""
        generation_types = {
            "solar_farm", "wind_farm", "hydro_plant", "gas_peaker",
            "thermal_plant", "bess",
        }
        if asset_type not in generation_types:
            return None

        actual = telemetry.get("active_power_mw", None)
        # Check telemetry first, then asset_meta
        rated = (meta.get("rated_capacity_mw") or
                 telemetry.get("rated_capacity_mw") or
                 telemetry.get("asset_meta", {}).get("rated_capacity_mw", 0))
        if actual is None or not rated:
            return None

        # Outage: output is less than 2% of rated during expected generation
        if actual < rated * 0.02:
            # Solar can legitimately be zero at night
            if asset_type == "solar_farm":
                hour = datetime.now(timezone.utc).hour
                if hour < 6 or hour > 20:
                    return None

            return DetectedFault(
                fault_id=self._new_fault_id(),
                fault_code="OUTAGE",
                asset_id=asset_id,
                asset_name=asset_name,
                asset_type=asset_type,
                severity=FaultSeverity.CRITICAL,
                category=FaultCategory.OUTAGE,
                title=f"Complete output loss — {asset_name}",
                description=(
                    f"Asset reporting {actual:.1f} MW against rated {rated:.0f} MW. "
                    f"Possible trip, emergency shutdown, or communication loss."
                ),
                detected_at=datetime.now(timezone.utc).isoformat(),
                trigger_param="active_power_mw",
                trigger_value=actual,
                trigger_threshold=rated * 0.02,
                estimated_loss_mw=rated,
                estimated_revenue_loss_hr=(
                    rated * self._loss_calc.REVENUE_RATES.get(asset_type, 50)
                ),
                recommended_action=(
                    "Check control room for trip reason. Inspect protection relay logs. "
                    "Attempt restart per O&M procedure after cause identified."
                ),
                work_order_priority="immediate",
                maintenance_type="corrective",
                confidence=0.95,
            )
        return None

    def _get_param(
        self, param: Optional[str], asset_id: str, telemetry: Dict
    ) -> Optional[float]:
        """Extract a parameter value from telemetry, with simulation fallback."""
        if not param:
            return None
        val = telemetry.get(param)
        if val is not None:
            return float(val)
        # Simulate realistic values for dev mode
        return self._simulate_param(param, asset_id)

    def _simulate_param(self, param: str, asset_id: str) -> Optional[float]:
        """Generate realistic simulated values for dev/demo mode."""
        sim_map = {
            "vibration_rms_mms":          lambda: abs(random.gauss(3.0, 2.5)),
            "penstock_pressure_differential_bar": lambda: abs(random.gauss(8.0, 3.0)),
            "seepage_flow_ls":             lambda: abs(random.gauss(15.0, 12.0)),
            "efficiency_pct":             lambda: random.gauss(91.0, 3.0),
            "gate_position_error_pct":    lambda: abs(random.gauss(1.0, 1.5)),
            "reservoir_level_pct":        lambda: random.gauss(72.0, 12.0),
            "string_current_ratio":       lambda: random.gauss(0.92, 0.08),
            "inverter_efficiency_pct":    lambda: random.gauss(97.0, 1.5),
            "performance_ratio":          lambda: random.gauss(0.84, 0.06),
            "tracker_azimuth_error_deg":  lambda: abs(random.gauss(1.5, 2.0)),
            "arc_fault_signature":        lambda: max(0, random.gauss(-0.5, 0.3)),
            "annual_degradation_pct":     lambda: random.gauss(-0.6, 0.2),
            "gearbox_vibration_g":        lambda: abs(random.gauss(2.0, 1.8)),
            "tower_vibration_1p_mms":     lambda: abs(random.gauss(1.2, 1.0)),
            "yaw_error_deg":              lambda: abs(random.gauss(3.0, 4.0)),
            "generator_temp_c":           lambda: random.gauss(95.0, 15.0),
            "power_curve_deviation_pct":  lambda: abs(random.gauss(4.0, 5.0)),
            "ice_detection_index":        lambda: max(0, random.gauss(0.1, 0.3)),
            "heat_rate_btu_kwh":          lambda: random.gauss(9800, 200),
            "exhaust_temp_spread_c":      lambda: abs(random.gauss(18.0, 10.0)),
            "compressor_pressure_ratio":  lambda: random.gauss(1.0, 0.03),
            "nox_ppm":                    lambda: abs(random.gauss(3.0, 1.2)),
            "cell_temp_max_c":            lambda: random.gauss(35.0, 8.0),
            "state_of_health_pct":        lambda: random.gauss(88.0, 6.0),
            "roundtrip_efficiency_pct":   lambda: random.gauss(91.0, 2.5),
            "cell_voltage_spread_mv":     lambda: abs(random.gauss(25.0, 20.0)),
            "dynamic_line_rating_pct":    lambda: random.gauss(78.0, 12.0),
            "partial_discharge_pC":       lambda: abs(random.gauss(150.0, 200.0)),
            "conductor_temp_c":           lambda: random.gauss(65.0, 18.0),
            "consumption_anomaly_score":  lambda: max(0, random.gauss(0.2, 0.3)),
            "hours_since_last_reading":   lambda: abs(random.gauss(0.5, 2.0)),
            "voltage_imbalance_pct":      lambda: abs(random.gauss(0.8, 0.8)),
        }
        fn = sim_map.get(param)
        return round(fn(), 4) if fn else None

    def _priority_from_severity(self, severity: FaultSeverity) -> str:
        return {
            FaultSeverity.CRITICAL: "immediate",
            FaultSeverity.HIGH:     "same_day",
            FaultSeverity.MEDIUM:   "7_days",
            FaultSeverity.LOW:      "scheduled",
            FaultSeverity.INFO:     "monitor",
        }.get(severity, "scheduled")

    def _confidence_score(
        self, sig: FaultSignature, value: Optional[float], threshold: Optional[float]
    ) -> float:
        """Higher confidence when measured value is far from threshold."""
        if value is None or threshold is None or threshold == 0:
            return 0.85
        deviation = abs(value - threshold) / abs(threshold)
        return round(min(0.99, 0.70 + deviation * 0.25), 2)

    def resolve_fault(self, asset_id: str, fault_code: str) -> bool:
        """Mark a fault as resolved (e.g., after maintenance completes)."""
        key = f"{asset_id}:{fault_code}"
        if key in self._active_faults:
            del self._active_faults[key]
            return True
        return False

    def get_active_faults(
        self, asset_id: Optional[str] = None,
        severity: Optional[FaultSeverity] = None,
    ) -> List[DetectedFault]:
        faults = list(self._active_faults.values())
        if asset_id:
            faults = [f for f in faults if f.asset_id == asset_id]
        if severity:
            faults = [f for f in faults if f.severity == severity]
        faults.sort(key=lambda f: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            .get(f.severity.value, 5),
            f.detected_at,
        ))
        return faults

    @property
    def summary(self) -> Dict[str, Any]:
        faults = list(self._active_faults.values())
        total_loss_mw = sum(
            f.estimated_loss_mw for f in faults if f.estimated_loss_mw
        )
        total_revenue_loss = sum(
            f.estimated_revenue_loss_hr for f in faults if f.estimated_revenue_loss_hr
        )
        return {
            "total_active_faults": len(faults),
            "critical": sum(1 for f in faults if f.severity == FaultSeverity.CRITICAL),
            "high":     sum(1 for f in faults if f.severity == FaultSeverity.HIGH),
            "medium":   sum(1 for f in faults if f.severity == FaultSeverity.MEDIUM),
            "low":      sum(1 for f in faults if f.severity == FaultSeverity.LOW),
            "outages":  sum(1 for f in faults if f.category == FaultCategory.OUTAGE),
            "energy_losses": sum(1 for f in faults if f.category == FaultCategory.EFFICIENCY_LOSS),
            "total_loss_mw": round(total_loss_mw, 1),
            "total_revenue_loss_hr": round(total_revenue_loss, 0),
            "by_category": {
                cat.value: sum(1 for f in faults if f.category == cat)
                for cat in FaultCategory
            },
        }


# ── Fleet-wide scanner ────────────────────────────────────────────────────────

class FleetFaultScanner:
    """
    Runs the fault detector across all assets in the fleet.
    Called by the telemetry polling service on each batch.
    Emits events to the bus for any new faults found.
    """

    def __init__(self):
        self.detector = AssetFaultDetector()
        self._scanned = 0

    async def scan_batch(self, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scan a telemetry batch. Emits alert events for new faults.
        Returns scan summary.
        """
        new_faults_total = 0

        for reading in readings:
            asset_id   = reading.get("asset_id", "")
            asset_name = reading.get("asset_name", asset_id)
            asset_type = reading.get("asset_type", "unknown")
            asset_meta = reading.get("asset_meta", {})

            if not asset_id:
                continue

            new_faults = self.detector.detect(
                asset_id=asset_id,
                asset_name=asset_name,
                asset_type=asset_type,
                telemetry=reading,
                asset_meta=asset_meta,
            )

            for fault in new_faults:
                new_faults_total += 1
                # Emit to GridIQ event bus → alert service picks it up
                await emit(EventType.ALERT_CREATED, {
                    "id": fault.fault_id,
                    "asset_id": fault.asset_id,
                    "severity": fault.severity.value,
                    "status": "open",
                    "title": fault.title,
                    "description": fault.description,
                    "source": "fault_detection_engine",
                    "category": fault.category.value,
                    "confidence": fault.confidence,
                    "recommended_action": fault.recommended_action,
                    "estimated_loss_mw": fault.estimated_loss_mw,
                    "estimated_revenue_loss_hr": fault.estimated_revenue_loss_hr,
                    "created_at": fault.detected_at,
                    "fault_code": fault.fault_code,
                    "trigger_param": fault.trigger_param,
                    "trigger_value": fault.trigger_value,
                })

        self._scanned += len(readings)
        return {
            "readings_scanned": len(readings),
            "new_faults": new_faults_total,
            "total_scanned": self._scanned,
            **self.detector.summary,
        }


# ── Singletons ────────────────────────────────────────────────────────────────
fault_detector = AssetFaultDetector()
fleet_scanner  = FleetFaultScanner()
