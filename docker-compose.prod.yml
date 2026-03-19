"""
GridIQ Sensor Management — Deployed Sensor Tracking
====================================================
Tracks every physical sensor deployed across the fleet:
  - Installation details (asset, location, installer)
  - Current status (online / degraded / offline)
  - Calibration schedule and history
  - Firmware version and connectivity
  - Data quality score (completeness, outlier rate, drift)
  - Maintenance history
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.sensors.catalog import (
    SENSOR_CATALOG, DeploymentStatus, SensorSpec,
    get_sensors_for_asset_type,
)

logger = logging.getLogger(__name__)


# ── Deployed sensor instance ──────────────────────────────────────────────────

@dataclass
class DeployedSensor:
    """
    A physical sensor installed at a specific asset.
    This is the live tracking record for one sensor unit.
    """
    sensor_id: str                   # unique ID e.g. "SEN-2026-0042"
    sensor_type_id: str              # reference to SensorSpec
    asset_id: str
    asset_name: str
    asset_type: str
    # Identity
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str
    # Location
    installation_point: str          # e.g. "Gearbox HS shaft NDE"
    lat: Optional[float] = None
    lon: Optional[float] = None
    # Status
    status: DeploymentStatus = DeploymentStatus.ONLINE
    # Dates
    install_date: str = ""
    last_calibration_date: Optional[str] = None
    next_calibration_date: Optional[str] = None
    last_seen: Optional[str] = None
    # Data quality (0-100)
    data_quality_score: float = 100.0
    availability_pct_30d: float = 99.5    # % of expected readings received
    outlier_rate_pct: float = 0.2         # % of readings flagged as outliers
    drift_detected: bool = False
    # Connectivity
    protocol: str = ""
    ip_address: Optional[str] = None
    signal_strength_dbm: Optional[float] = None
    # Commercial
    purchase_cost_usd: Optional[int] = None
    warranty_expiry: Optional[str] = None
    # Notes
    notes: str = ""
    alerts: List[str] = field(default_factory=list)


# ── Data quality scorer ───────────────────────────────────────────────────────

class DataQualityScorer:
    """
    Computes a 0–100 data quality score for each sensor based on:
    - Availability (% of expected readings arriving)
    - Outlier rate (% of readings outside physical plausibility)
    - Drift (calibration drift detected vs. reference)
    - Communication gaps
    - Firmware health
    """

    def score(self, sensor: DeployedSensor) -> float:
        score = 100.0

        # Availability penalty
        if sensor.availability_pct_30d < 99:
            score -= (99 - sensor.availability_pct_30d) * 2
        if sensor.availability_pct_30d < 95:
            score -= 15

        # Outlier rate penalty
        score -= min(20, sensor.outlier_rate_pct * 10)

        # Drift penalty
        if sensor.drift_detected:
            score -= 20

        # Calibration overdue penalty
        if sensor.next_calibration_date:
            try:
                next_cal = datetime.fromisoformat(sensor.next_calibration_date)
                days_overdue = (datetime.now(timezone.utc) - next_cal.replace(tzinfo=timezone.utc)).days
                if days_overdue > 0:
                    score -= min(25, days_overdue / 10)
            except Exception:
                pass

        # Status penalty
        if sensor.status == DeploymentStatus.DEGRADED:
            score -= 15
        elif sensor.status == DeploymentStatus.OFFLINE:
            score -= 50

        return max(0.0, round(score, 1))

    def quality_label(self, score: float) -> str:
        if score >= 95: return "excellent"
        elif score >= 85: return "good"
        elif score >= 70: return "fair"
        elif score >= 50: return "poor"
        else: return "critical"

    def alerts_for_sensor(self, sensor: DeployedSensor) -> List[str]:
        alerts = []
        if sensor.availability_pct_30d < 95:
            alerts.append(f"Low availability: {sensor.availability_pct_30d:.1f}% (30d)")
        if sensor.outlier_rate_pct > 2:
            alerts.append(f"High outlier rate: {sensor.outlier_rate_pct:.1f}%")
        if sensor.drift_detected:
            alerts.append("Calibration drift detected — recalibration required")
        if sensor.status == DeploymentStatus.OFFLINE:
            alerts.append("Sensor offline — no data received")
        if sensor.status == DeploymentStatus.DEGRADED:
            alerts.append("Sensor degraded — reduced accuracy")
        if sensor.next_calibration_date:
            try:
                next_cal = datetime.fromisoformat(sensor.next_calibration_date)
                days = (next_cal.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
                if days < 0:
                    alerts.append(f"Calibration {abs(days)} days overdue")
                elif days < 30:
                    alerts.append(f"Calibration due in {days} days")
            except Exception:
                pass
        return alerts


# ── Sensor registry ───────────────────────────────────────────────────────────

class SensorRegistry:
    """
    In-memory registry of all deployed sensors.
    In production: backed by PostgreSQL.
    """

    def __init__(self):
        self._sensors: Dict[str, DeployedSensor] = {}
        self._scorer = DataQualityScorer()
        self._counter = 0
        # Seed demo data on init
        self._seed_demo_sensors()

    def _new_id(self) -> str:
        self._counter += 1
        return f"SEN-{datetime.now(timezone.utc).year}-{self._counter:04d}"

    def register(self, sensor: DeployedSensor) -> DeployedSensor:
        if not sensor.sensor_id:
            sensor.sensor_id = self._new_id()
        # Compute initial quality score
        sensor.data_quality_score = self._scorer.score(sensor)
        sensor.alerts = self._scorer.alerts_for_sensor(sensor)
        self._sensors[sensor.sensor_id] = sensor
        logger.info(f"[SensorRegistry] Registered {sensor.sensor_id} on {sensor.asset_name}")
        return sensor

    def get(self, sensor_id: str) -> Optional[DeployedSensor]:
        return self._sensors.get(sensor_id)

    def list_all(self,
                 asset_id: Optional[str] = None,
                 asset_type: Optional[str] = None,
                 status: Optional[str] = None,
                 category: Optional[str] = None,
                 quality_below: Optional[float] = None) -> List[DeployedSensor]:
        sensors = list(self._sensors.values())
        if asset_id:
            sensors = [s for s in sensors if s.asset_id == asset_id]
        if asset_type:
            sensors = [s for s in sensors if s.asset_type == asset_type]
        if status:
            sensors = [s for s in sensors if s.status.value == status]
        if quality_below:
            sensors = [s for s in sensors if s.data_quality_score < quality_below]
        return sensors

    def update_status(self, sensor_id: str, status: DeploymentStatus) -> Optional[DeployedSensor]:
        s = self._sensors.get(sensor_id)
        if s:
            s.status = status
            s.last_seen = datetime.now(timezone.utc).isoformat()
            s.data_quality_score = self._scorer.score(s)
            s.alerts = self._scorer.alerts_for_sensor(s)
        return s

    def record_calibration(self, sensor_id: str, cal_date: Optional[str] = None) -> Optional[DeployedSensor]:
        s = self._sensors.get(sensor_id)
        if not s:
            return None
        spec = next((sp for sp in SENSOR_CATALOG if sp.sensor_type_id == s.sensor_type_id), None)
        s.last_calibration_date = cal_date or datetime.now(timezone.utc).isoformat()
        s.drift_detected = False
        # Set next calibration date based on spec frequency
        freq_days = {
            "monthly": 30, "quarterly": 90, "annual": 365,
            "biannual": 730, "on_demand": 365,
        }
        if spec:
            days = freq_days.get(spec.calibration_frequency.value, 365)
            next_dt = datetime.now(timezone.utc) + timedelta(days=days)
            s.next_calibration_date = next_dt.isoformat()
        s.data_quality_score = self._scorer.score(s)
        s.alerts = self._scorer.alerts_for_sensor(s)
        logger.info(f"[SensorRegistry] Calibration recorded for {sensor_id}")
        return s

    def summary(self) -> Dict[str, Any]:
        sensors = list(self._sensors.values())
        if not sensors:
            return {"total": 0}
        online  = sum(1 for s in sensors if s.status == DeploymentStatus.ONLINE)
        offline = sum(1 for s in sensors if s.status == DeploymentStatus.OFFLINE)
        degraded= sum(1 for s in sensors if s.status == DeploymentStatus.DEGRADED)
        cal_due = sum(1 for s in sensors if _is_cal_overdue(s))
        avg_quality = sum(s.data_quality_score for s in sensors) / len(sensors)
        poor_quality = sum(1 for s in sensors if s.data_quality_score < 70)

        return {
            "total_sensors":        len(sensors),
            "online":               online,
            "offline":              offline,
            "degraded":             degraded,
            "calibration_due":      cal_due,
            "avg_data_quality":     round(avg_quality, 1),
            "poor_quality_count":   poor_quality,
            "fleet_availability_pct": round(online / len(sensors) * 100, 1),
        }

    def calibration_schedule(self) -> List[Dict]:
        """Return sensors due for calibration in the next 90 days, sorted by urgency."""
        due = []
        for s in self._sensors.values():
            if not s.next_calibration_date:
                continue
            try:
                next_cal = datetime.fromisoformat(s.next_calibration_date)
                days = (next_cal.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
                if days <= 90:
                    due.append({
                        "sensor_id": s.sensor_id,
                        "asset_name": s.asset_name,
                        "sensor_type_id": s.sensor_type_id,
                        "installation_point": s.installation_point,
                        "days_until_due": days,
                        "overdue": days < 0,
                        "next_calibration_date": s.next_calibration_date,
                        "last_calibration_date": s.last_calibration_date,
                    })
            except Exception:
                pass
        due.sort(key=lambda x: x["days_until_due"])
        return due

    def _seed_demo_sensors(self):
        """Populate with realistic demo sensor fleet."""
        now = datetime.now(timezone.utc)

        demo = [
            # ── Hydro / Dam ────────────────────────────────────────────────
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="ME-001",
                asset_id="hydro-001", asset_name="Shasta Dam Unit 3",
                asset_type="hydro_plant",
                manufacturer="SKF", model="CMSS 793A",
                serial_number="SKF-2021-44821", firmware_version="3.2.1",
                installation_point="Turbine runner bearing (guide bearing)",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=1460)).isoformat(),
                last_calibration_date=(now - timedelta(days=280)).isoformat(),
                next_calibration_date=(now + timedelta(days=85)).isoformat(),
                availability_pct_30d=99.8, outlier_rate_pct=0.1,
                protocol="modbus_tcp", ip_address="10.10.1.101",
                purchase_cost_usd=620, notes="High vibration flag triggered HYD-001",
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="HY-002",
                asset_id="dam-001", asset_name="Folsom Dam",
                asset_type="dam",
                manufacturer="Campbell Scientific", model="CS450",
                serial_number="CSI-2022-88312", firmware_version="2.1.0",
                installation_point="Right abutment drainage gallery — piezometer P-07",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=730)).isoformat(),
                last_calibration_date=(now - timedelta(days=200)).isoformat(),
                next_calibration_date=(now + timedelta(days=165)).isoformat(),
                availability_pct_30d=100.0, outlier_rate_pct=0.0,
                protocol="sdi_12",
                purchase_cost_usd=850,
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="HY-001",
                asset_id="dam-001", asset_name="Folsom Dam",
                asset_type="dam",
                manufacturer="Vega", model="VEGAPULS 64",
                serial_number="VGA-2020-11234", firmware_version="1.8.3",
                installation_point="Forebay — stilling well level sensor",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=2000)).isoformat(),
                last_calibration_date=(now - timedelta(days=380)).isoformat(),
                next_calibration_date=(now - timedelta(days=15)).isoformat(),  # OVERDUE
                availability_pct_30d=98.2, outlier_rate_pct=0.3,
                drift_detected=True,
                protocol="hart",
                purchase_cost_usd=3200,
            ),

            # ── Solar Farm ────────────────────────────────────────────────
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="EL-002",
                asset_id="solar-001", asset_name="Solar Farm Alpha",
                asset_type="solar_farm",
                manufacturer="IMO Precision", model="SM-200",
                serial_number="IMO-2023-55541", firmware_version="4.0.1",
                installation_point="Combiner box CB-14 — strings 1-8",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=365)).isoformat(),
                last_calibration_date=(now - timedelta(days=300)).isoformat(),
                next_calibration_date=(now + timedelta(days=65)).isoformat(),
                availability_pct_30d=99.9, outlier_rate_pct=0.2,
                protocol="modbus_rtu",
                purchase_cost_usd=120,
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="EN-001",
                asset_id="solar-001", asset_name="Solar Farm Alpha",
                asset_type="solar_farm",
                manufacturer="Kipp & Zonen", model="CMP11",
                serial_number="KZ-2022-77123", firmware_version="N/A",
                installation_point="Met station — tracker row 12 (center field)",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=800)).isoformat(),
                last_calibration_date=(now - timedelta(days=250)).isoformat(),
                next_calibration_date=(now + timedelta(days=115)).isoformat(),
                availability_pct_30d=99.7, outlier_rate_pct=0.1,
                protocol="modbus_rtu",
                purchase_cost_usd=2800,
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="EL-003",
                asset_id="solar-001", asset_name="Solar Farm Alpha",
                asset_type="solar_farm",
                manufacturer="Qualitrol", model="509 NTPD",
                serial_number="QLT-2023-20011", firmware_version="5.1.2",
                installation_point="Main step-up transformer T1 — HV bushing",
                status=DeploymentStatus.DEGRADED,
                install_date=(now - timedelta(days=500)).isoformat(),
                last_calibration_date=(now - timedelta(days=120)).isoformat(),
                next_calibration_date=(now + timedelta(days=245)).isoformat(),
                availability_pct_30d=88.5, outlier_rate_pct=3.2,
                protocol="modbus_tcp", ip_address="10.20.5.44",
                purchase_cost_usd=1400,
                notes="Communication drops intermittently — check cable integrity",
            ),

            # ── Wind Farm ─────────────────────────────────────────────────
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="ME-001",
                asset_id="wind-001", asset_name="Wind Farm North T-12",
                asset_type="wind_farm",
                manufacturer="Brüel & Kjær", model="Type 4514-B-001",
                serial_number="BK-2022-33987", firmware_version="2.4.0",
                installation_point="Gearbox high-speed shaft NDE bearing",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=600)).isoformat(),
                last_calibration_date=(now - timedelta(days=180)).isoformat(),
                next_calibration_date=(now + timedelta(days=185)).isoformat(),
                availability_pct_30d=99.5, outlier_rate_pct=0.4,
                protocol="modbus_tcp", ip_address="10.30.1.12",
                purchase_cost_usd=580,
                notes="Elevated BPFO signature — WND-001 active",
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="ME-003",
                asset_id="wind-001", asset_name="Wind Farm North T-12",
                asset_type="wind_farm",
                manufacturer="Heidenhain", model="ERN 1387",
                serial_number="HH-2021-99012", firmware_version="1.0",
                installation_point="Main shaft encoder — 2048 PPR",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=1200)).isoformat(),
                last_calibration_date=(now - timedelta(days=310)).isoformat(),
                next_calibration_date=(now + timedelta(days=55)).isoformat(),
                availability_pct_30d=100.0, outlier_rate_pct=0.0,
                protocol="htl_pulse",
                purchase_cost_usd=420,
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="EN-002",
                asset_id="wind-001", asset_name="Wind Farm North",
                asset_type="wind_farm",
                manufacturer="Vaisala", model="WXT536",
                serial_number="VAI-2023-10089", firmware_version="3.2",
                installation_point="Met mast 80m hub height — north turbine row",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=400)).isoformat(),
                last_calibration_date=(now - timedelta(days=100)).isoformat(),
                next_calibration_date=(now + timedelta(days=265)).isoformat(),
                availability_pct_30d=99.1, outlier_rate_pct=0.2,
                protocol="modbus_rtu",
                purchase_cost_usd=4200,
            ),

            # ── BESS ──────────────────────────────────────────────────────
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="EL-005",
                asset_id="bess-001", asset_name="BESS-1 Tesla Megapack",
                asset_type="bess",
                manufacturer="Tesla", model="Megapack 2XL BMS",
                serial_number="TSL-2024-MP-00142", firmware_version="24.12.1",
                installation_point="BMS gateway — all modules",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=180)).isoformat(),
                last_calibration_date=(now - timedelta(days=60)).isoformat(),
                next_calibration_date=(now + timedelta(days=120)).isoformat(),
                availability_pct_30d=99.9, outlier_rate_pct=0.05,
                protocol="rest_api",
                purchase_cost_usd=15000,
                notes="Tesla Fleet API v3 — cell-level data at 10Hz",
            ),

            # ── Transformer DGA ───────────────────────────────────────────
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="CH-001",
                asset_id="asset-001", asset_name="Transformer T-01A",
                asset_type="transformer",
                manufacturer="GE Kelman", model="TRANSFIX",
                serial_number="GEK-2022-44217", firmware_version="6.1.0",
                installation_point="Top oil sampling valve — transformer body",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=900)).isoformat(),
                last_calibration_date=(now - timedelta(days=320)).isoformat(),
                next_calibration_date=(now + timedelta(days=45)).isoformat(),
                availability_pct_30d=99.6, outlier_rate_pct=0.1,
                protocol="modbus_tcp", ip_address="10.55.2.10",
                purchase_cost_usd=18000,
                notes="Ethylene rising — possible thermal fault developing",
            ),

            # ── Transmission ──────────────────────────────────────────────
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="ME-005",
                asset_id="txn-001", asset_name="Sierra 230kV Line",
                asset_type="transmission_line",
                manufacturer="Lindsey Systems", model="CAT-1 RTMAM",
                serial_number="LIN-2023-78001", firmware_version="2.0.3",
                installation_point="Span 14 — mid-span tension monitor",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=550)).isoformat(),
                last_calibration_date=(now - timedelta(days=200)).isoformat(),
                next_calibration_date=(now + timedelta(days=165)).isoformat(),
                availability_pct_30d=97.8, outlier_rate_pct=0.8,
                protocol="gsm_4g",
                purchase_cost_usd=8500,
            ),
            DeployedSensor(
                sensor_id=self._new_id(), sensor_type_id="EL-003",
                asset_id="txn-001", asset_name="Sierra 230kV Line",
                asset_type="transmission_line",
                manufacturer="Doble Engineering", model="M7200",
                serial_number="DBL-2021-22001", firmware_version="4.3.2",
                installation_point="Tower 22 — insulator string HFCT",
                status=DeploymentStatus.ONLINE,
                install_date=(now - timedelta(days=1100)).isoformat(),
                last_calibration_date=(now - timedelta(days=290)).isoformat(),
                next_calibration_date=(now + timedelta(days=75)).isoformat(),
                availability_pct_30d=99.3, outlier_rate_pct=0.2,
                protocol="industrial_ethernet", ip_address="10.44.8.22",
                purchase_cost_usd=1800,
                notes="PD readings elevated — TXN-002 active",
            ),
        ]

        for s in demo:
            s.data_quality_score = DataQualityScorer().score(s)
            s.alerts = DataQualityScorer().alerts_for_sensor(s)
            self._sensors[s.sensor_id] = s

        logger.info(f"[SensorRegistry] Seeded {len(self._sensors)} demo sensors")


def _is_cal_overdue(s: DeployedSensor) -> bool:
    if not s.next_calibration_date:
        return False
    try:
        return datetime.fromisoformat(s.next_calibration_date).replace(
            tzinfo=timezone.utc
        ) < datetime.now(timezone.utc)
    except Exception:
        return False


# ── Singleton ─────────────────────────────────────────────────────────────────
sensor_registry = SensorRegistry()
