"""
GridIQ Asset Intelligence — Asset Type Models
==============================================
Defines inspection parameters, fault signatures, efficiency models,
and health metrics for every energy asset type on the grid.

Each asset type knows:
  - What sensors/readings it produces
  - What "healthy" looks like vs. degraded vs. failed
  - What faults are detectable from telemetry
  - What maintenance triggers apply

Asset types covered:
  DAM / HYDRO     — structural, hydraulic, electrical
  SOLAR FARM      — panel, inverter, string, tracker
  WIND FARM       — turbine mechanical, electrical, blade, gearbox
  GAS PEAKER      — combustion, compression, exhaust, cooling
  BESS            — cell health, thermal, cycling, BMS
  SUBSTATION      — transformer, breaker, relay, capacitor, RTU
  TRANSMISSION    — conductor, hardware, sag, corona (+ vegetation from veg module)
  SMART METER     — comms, tampering, accuracy, load
  HYDRO PIPELINE  — penstock pressure, valve, surge
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ── Fault severity levels ─────────────────────────────────────────────────────

class FaultSeverity(str, Enum):
    CRITICAL  = "critical"   # Immediate shutdown / dispatch
    HIGH      = "high"       # Same-day response
    MEDIUM    = "medium"     # Within 7 days
    LOW       = "low"        # Next scheduled maintenance
    INFO      = "info"       # Monitor / trend


# ── Fault categories ──────────────────────────────────────────────────────────

class FaultCategory(str, Enum):
    OUTAGE         = "outage"          # Complete loss of output
    PARTIAL_LOSS   = "partial_loss"    # Reduced output
    EFFICIENCY_LOSS= "efficiency_loss" # Output below theoretical
    MECHANICAL     = "mechanical"      # Physical component fault
    ELECTRICAL     = "electrical"      # Electrical fault / anomaly
    THERMAL        = "thermal"         # Temperature out of range
    STRUCTURAL     = "structural"      # Physical structure integrity
    HYDRAULIC      = "hydraulic"       # Fluid/pressure system
    COMMUNICATION  = "communication"   # Sensor/SCADA comm loss
    SECURITY       = "security"        # Tampering / theft
    ENVIRONMENTAL  = "environmental"   # Weather / vegetation / flooding
    COMPLIANCE     = "compliance"      # Regulatory / permit issue


# ── Fault signature ───────────────────────────────────────────────────────────

@dataclass
class FaultSignature:
    """
    Defines a detectable fault pattern for an asset type.
    The detection engine matches incoming telemetry against these signatures.
    """
    fault_code: str
    name: str
    asset_types: List[str]           # which asset types this applies to
    category: FaultCategory
    severity: FaultSeverity
    description: str
    detection_method: str            # threshold | trend | ratio | ml_anomaly | vibration_fft
    # Detection parameters
    threshold_param: Optional[str] = None    # telemetry field to check
    threshold_lo: Optional[float] = None     # below this = fault
    threshold_hi: Optional[float] = None     # above this = fault
    trend_window_hours: Optional[int] = None # for trend-based detection
    trend_slope_threshold: Optional[float] = None  # m/hour for trend
    # Context
    nerc_standard: Optional[str] = None     # applicable NERC standard
    estimated_loss_mw: Optional[float] = None
    recommended_action: str = ""
    maintenance_type: str = "corrective"     # predictive | corrective | emergency


# ── Master fault signature library ───────────────────────────────────────────

FAULT_SIGNATURES: List[FaultSignature] = [

    # ── DAM / HYDRO ──────────────────────────────────────────────────────────
    FaultSignature(
        fault_code="HYD-001", name="Turbine cavitation detected",
        asset_types=["hydro_plant", "dam"],
        category=FaultCategory.MECHANICAL, severity=FaultSeverity.HIGH,
        description="Vibration signature consistent with cavitation in runner blades. Continued operation causes rapid erosion.",
        detection_method="vibration_fft",
        threshold_param="vibration_rms_mms", threshold_hi=8.5,
        recommended_action="Reduce load by 20%. Schedule runner inspection within 72h.",
        estimated_loss_mw=15.0, nerc_standard="FAC-001",
    ),
    FaultSignature(
        fault_code="HYD-002", name="Head loss exceeding design — penstock obstruction",
        asset_types=["hydro_plant", "dam"],
        category=FaultCategory.HYDRAULIC, severity=FaultSeverity.MEDIUM,
        description="Differential pressure across penstock higher than design curve. Possible debris obstruction or corrosion buildup.",
        detection_method="ratio",
        threshold_param="penstock_pressure_differential_bar", threshold_hi=12.0,
        recommended_action="Inspect trash racks and intake screens. Schedule penstock internal inspection.",
        estimated_loss_mw=8.0,
    ),
    FaultSignature(
        fault_code="HYD-003", name="Dam seepage rate elevated",
        asset_types=["dam"],
        category=FaultCategory.STRUCTURAL, severity=FaultSeverity.CRITICAL,
        description="Downstream seepage measuring devices show flow above baseline. Potential embankment piping or foundation issue.",
        detection_method="threshold",
        threshold_param="seepage_flow_ls", threshold_hi=45.0,
        recommended_action="IMMEDIATE: Notify dam safety engineer. Begin enhanced monitoring. Prepare emergency action plan.",
        nerc_standard="FERC Part 12",
    ),
    FaultSignature(
        fault_code="HYD-004", name="Generator efficiency degradation",
        asset_types=["hydro_plant"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.MEDIUM,
        description="Actual output vs. theoretical output from water flow and head has declined >5% over 30 days.",
        detection_method="trend",
        threshold_param="efficiency_pct", trend_window_hours=720,
        trend_slope_threshold=-0.008,
        recommended_action="Schedule runner and wicket gate inspection at next planned outage.",
        estimated_loss_mw=5.0, maintenance_type="predictive",
    ),
    FaultSignature(
        fault_code="HYD-005", name="Spillway gate actuator fault",
        asset_types=["dam"],
        category=FaultCategory.MECHANICAL, severity=FaultSeverity.HIGH,
        description="Gate position sensor and command signal mismatch. Gate may not open fully during flood event.",
        detection_method="threshold",
        threshold_param="gate_position_error_pct", threshold_hi=5.0,
        recommended_action="Inspect gate mechanism. Test manual override. Critical for flood control.",
    ),
    FaultSignature(
        fault_code="HYD-006", name="Reservoir level declining — drought curtailment risk",
        asset_types=["dam", "hydro_plant"],
        category=FaultCategory.ENVIRONMENTAL, severity=FaultSeverity.MEDIUM,
        description="Reservoir level 15% below seasonal average. Output curtailment within 45 days at current inflow rate.",
        detection_method="trend",
        threshold_param="reservoir_level_pct", trend_slope_threshold=-0.3,
        recommended_action="Notify dispatch. Adjust generation schedule. Coordinate with water authority.",
        estimated_loss_mw=20.0,
    ),

    # ── SOLAR FARM ───────────────────────────────────────────────────────────
    FaultSignature(
        fault_code="SOL-001", name="String-level dropout — inverter input fault",
        asset_types=["solar_farm"],
        category=FaultCategory.PARTIAL_LOSS, severity=FaultSeverity.HIGH,
        description="One or more DC strings showing zero current despite irradiance >200 W/m². Possible string fuse, connector, or panel failure.",
        detection_method="threshold",
        threshold_param="string_current_ratio", threshold_lo=0.05,
        recommended_action="Dispatch technician with IV curve tracer. Check string fuses and connectors.",
        estimated_loss_mw=0.8, maintenance_type="corrective",
    ),
    FaultSignature(
        fault_code="SOL-002", name="Inverter efficiency below nameplate",
        asset_types=["solar_farm"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.MEDIUM,
        description="Inverter DC→AC conversion efficiency below 95% (nameplate 98%). Possible IGBT degradation or cooling issue.",
        detection_method="ratio",
        threshold_param="inverter_efficiency_pct", threshold_lo=95.0,
        recommended_action="Check inverter cooling fans and heat sink. Schedule IGBT inspection.",
        estimated_loss_mw=1.5,
    ),
    FaultSignature(
        fault_code="SOL-003", name="Soiling loss exceeding 5% — cleaning required",
        asset_types=["solar_farm"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.LOW,
        description="Actual irradiance-normalized output is 5–15% below clean-panel baseline. Panel soiling (dust, bird droppings, pollen).",
        detection_method="ratio",
        threshold_param="performance_ratio", threshold_lo=0.78,
        recommended_action="Schedule panel cleaning. Check tilt angle for self-cleaning effectiveness.",
        estimated_loss_mw=3.0, maintenance_type="predictive",
    ),
    FaultSignature(
        fault_code="SOL-004", name="Tracker misalignment — mechanical fault",
        asset_types=["solar_farm"],
        category=FaultCategory.MECHANICAL, severity=FaultSeverity.MEDIUM,
        description="Single-axis tracker azimuth deviation >5° from optimal. Actuator or encoder fault.",
        detection_method="threshold",
        threshold_param="tracker_azimuth_error_deg", threshold_hi=5.0,
        recommended_action="Inspect tracker actuator and limit switches. Check weather vane inputs.",
        estimated_loss_mw=2.0,
    ),
    FaultSignature(
        fault_code="SOL-005", name="DC arc fault detected",
        asset_types=["solar_farm"],
        category=FaultCategory.ELECTRICAL, severity=FaultSeverity.CRITICAL,
        description="Arc fault current signature detected on DC combiner. Fire risk — immediate de-energization required.",
        detection_method="ml_anomaly",
        threshold_param="arc_fault_signature", threshold_hi=1.0,
        recommended_action="EMERGENCY: Isolate affected combiner. Inspect for hot spots with thermal camera. Fire risk.",
        nerc_standard="NEC 690",
    ),
    FaultSignature(
        fault_code="SOL-006", name="PV panel degradation rate elevated",
        asset_types=["solar_farm"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.LOW,
        description="Year-over-year performance ratio decline >1% per year (industry norm 0.5%/yr). Possible LID, PID, or micro-cracking.",
        detection_method="trend",
        threshold_param="annual_degradation_pct", trend_window_hours=8760,
        trend_slope_threshold=-0.001,
        recommended_action="EL (electroluminescence) imaging at next maintenance window. Review warranty terms.",
        maintenance_type="predictive",
    ),

    # ── WIND FARM ────────────────────────────────────────────────────────────
    FaultSignature(
        fault_code="WND-001", name="Gearbox vibration — bearing fault signature",
        asset_types=["wind_farm"],
        category=FaultCategory.MECHANICAL, severity=FaultSeverity.HIGH,
        description="High-speed shaft bearing vibration showing BPFO/BPFI signature. Bearing failure precursor. Typical lead time 2–8 weeks.",
        detection_method="vibration_fft",
        threshold_param="gearbox_vibration_g", threshold_hi=4.5,
        recommended_action="Oil sample analysis. Schedule bearing inspection within 14 days. Monitor every 48h.",
        estimated_loss_mw=2.5, maintenance_type="predictive",
    ),
    FaultSignature(
        fault_code="WND-002", name="Blade imbalance — mass or aerodynamic",
        asset_types=["wind_farm"],
        category=FaultCategory.MECHANICAL, severity=FaultSeverity.HIGH,
        description="1P vibration component elevated. Possible ice accretion, leading edge erosion, or pitch system fault.",
        detection_method="vibration_fft",
        threshold_param="tower_vibration_1p_mms", threshold_hi=3.0,
        recommended_action="Inspect blade pitch angles. Thermal imaging for ice. Drone inspection for LE erosion.",
        estimated_loss_mw=1.8,
    ),
    FaultSignature(
        fault_code="WND-003", name="Yaw misalignment — wind direction offset",
        asset_types=["wind_farm"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.MEDIUM,
        description="Nacelle direction persistently offset >8° from wind vane reading. Yaw motor or encoder fault.",
        detection_method="threshold",
        threshold_param="yaw_error_deg", threshold_hi=8.0,
        recommended_action="Calibrate wind vane. Inspect yaw drive encoder. Check for loose bolts.",
        estimated_loss_mw=1.2,
    ),
    FaultSignature(
        fault_code="WND-004", name="Generator stator temperature high",
        asset_types=["wind_farm"],
        category=FaultCategory.THERMAL, severity=FaultSeverity.HIGH,
        description="Stator winding temperature >120°C. Insulation degradation accelerates above this threshold.",
        detection_method="threshold",
        threshold_param="generator_temp_c", threshold_hi=120.0,
        recommended_action="Reduce load 20%. Check cooling circuit. Thermal camera inspection of windings.",
        estimated_loss_mw=2.0,
    ),
    FaultSignature(
        fault_code="WND-005", name="Turbine output below power curve",
        asset_types=["wind_farm"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.MEDIUM,
        description="Actual power output >10% below expected power curve for measured wind speed. Multiple possible causes.",
        detection_method="ratio",
        threshold_param="power_curve_deviation_pct", threshold_hi=10.0,
        recommended_action="Check blade pitch calibration, curtailment settings, and sensor calibration.",
        estimated_loss_mw=1.5, maintenance_type="predictive",
    ),
    FaultSignature(
        fault_code="WND-006", name="Ice detection — blade icing event",
        asset_types=["wind_farm"],
        category=FaultCategory.ENVIRONMENTAL, severity=FaultSeverity.HIGH,
        description="Vibration + power output signature consistent with ice accretion on blades. Safety stop required.",
        detection_method="ml_anomaly",
        threshold_param="ice_detection_index", threshold_hi=0.7,
        recommended_action="Stop affected turbines. Activate blade heating if available. Inspect after thaw.",
        estimated_loss_mw=2.5,
    ),

    # ── GAS PEAKER / THERMAL ─────────────────────────────────────────────────
    FaultSignature(
        fault_code="GAS-001", name="Heat rate degradation — combustion inefficiency",
        asset_types=["gas_peaker", "thermal_plant"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.MEDIUM,
        description="Heat rate (BTU/kWh) elevated >3% above design. Compressor fouling or combustion tuning drift.",
        detection_method="trend",
        threshold_param="heat_rate_btu_kwh", trend_window_hours=168,
        trend_slope_threshold=0.02,
        recommended_action="Compressor water wash. Re-tune combustion. Check fuel quality.",
        estimated_loss_mw=5.0,
    ),
    FaultSignature(
        fault_code="GAS-002", name="Exhaust temperature spread — hot section fault",
        asset_types=["gas_peaker", "thermal_plant"],
        category=FaultCategory.THERMAL, severity=FaultSeverity.HIGH,
        description="Exhaust thermocouple spread exceeding 30°C. Indicates combustor or transition piece issue.",
        detection_method="threshold",
        threshold_param="exhaust_temp_spread_c", threshold_hi=30.0,
        recommended_action="Reduce load. Borescope inspection of combustion section at next opportunity.",
        estimated_loss_mw=8.0,
    ),
    FaultSignature(
        fault_code="GAS-003", name="Compressor discharge pressure low",
        asset_types=["gas_peaker", "thermal_plant"],
        category=FaultCategory.MECHANICAL, severity=FaultSeverity.HIGH,
        description="Compressor discharge pressure ratio below design. Blade fouling, damage, or variable stator vane issue.",
        detection_method="threshold",
        threshold_param="compressor_pressure_ratio", threshold_lo=0.95,
        recommended_action="Inspect variable stator vanes. Water wash compressor. Check inlet filter.",
    ),
    FaultSignature(
        fault_code="GAS-004", name="NOx emissions approaching permit limit",
        asset_types=["gas_peaker", "thermal_plant"],
        category=FaultCategory.COMPLIANCE, severity=FaultSeverity.HIGH,
        description="NOx emissions within 10% of permit limit. Combustion tuning or water injection adjustment needed.",
        detection_method="threshold",
        threshold_param="nox_ppm", threshold_hi=4.5,
        recommended_action="Adjust combustion tuning. Increase water/steam injection rate. Notify environmental compliance.",
        nerc_standard="EPA 40 CFR 60",
    ),

    # ── BATTERY STORAGE (BESS) ────────────────────────────────────────────────
    FaultSignature(
        fault_code="BSS-001", name="Cell thermal runaway precursor",
        asset_types=["bess"],
        category=FaultCategory.THERMAL, severity=FaultSeverity.CRITICAL,
        description="Cell temperature exceeding 50°C with rising trend. BMS voltage deviation detected. Thermal runaway risk.",
        detection_method="threshold",
        threshold_param="cell_temp_max_c", threshold_hi=50.0,
        recommended_action="EMERGENCY: Activate fire suppression standby. Reduce charge rate to zero. Notify fire department.",
    ),
    FaultSignature(
        fault_code="BSS-002", name="State of health below 80% — capacity loss",
        asset_types=["bess"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.MEDIUM,
        description="Battery state of health below 80% of nameplate capacity. Usable energy storage significantly reduced.",
        detection_method="threshold",
        threshold_param="state_of_health_pct", threshold_lo=80.0,
        recommended_action="Review dispatch plan. Reduce depth of discharge. Plan capacity augmentation or replacement.",
        maintenance_type="predictive",
    ),
    FaultSignature(
        fault_code="BSS-003", name="Round-trip efficiency degradation",
        asset_types=["bess"],
        category=FaultCategory.EFFICIENCY_LOSS, severity=FaultSeverity.LOW,
        description="Measured round-trip efficiency below 88% (nameplate 92%). Increased parasitic losses.",
        detection_method="ratio",
        threshold_param="roundtrip_efficiency_pct", threshold_lo=88.0,
        recommended_action="Check BMS firmware. Inspect contactors and cable connections. Review thermal management.",
        maintenance_type="predictive",
    ),
    FaultSignature(
        fault_code="BSS-004", name="Cell voltage imbalance — BMS fault",
        asset_types=["bess"],
        category=FaultCategory.ELECTRICAL, severity=FaultSeverity.HIGH,
        description="Cell voltage spread >50mV within a module. Indicates cell failure or BMS balancing circuit fault.",
        detection_method="threshold",
        threshold_param="cell_voltage_spread_mv", threshold_hi=50.0,
        recommended_action="Force balance cycle. Inspect affected module. Replace cells if imbalance persists.",
    ),

    # ── TRANSMISSION / CONDUCTOR ──────────────────────────────────────────────
    FaultSignature(
        fault_code="TXN-001", name="Conductor sag exceeding clearance limit",
        asset_types=["transmission_line", "substation"],
        category=FaultCategory.STRUCTURAL, severity=FaultSeverity.CRITICAL,
        description="Real-time sag model exceeds ground clearance minimum at maximum load/temperature.",
        detection_method="threshold",
        threshold_param="dynamic_line_rating_pct", threshold_hi=100.0,
        recommended_action="Reduce line loading immediately. Inspect structure for settlement. Re-tension conductor.",
        nerc_standard="NERC FAC-001",
    ),
    FaultSignature(
        fault_code="TXN-002", name="Partial discharge detected — insulator degradation",
        asset_types=["transmission_line", "substation"],
        category=FaultCategory.ELECTRICAL, severity=FaultSeverity.HIGH,
        description="Partial discharge measurement elevated. Corona or tracking on insulator string. Flashover risk.",
        detection_method="threshold",
        threshold_param="partial_discharge_pC", threshold_hi=500.0,
        recommended_action="UV corona camera inspection. Replace suspect insulators at next outage.",
    ),
    FaultSignature(
        fault_code="TXN-003", name="Conductor temperature high — ampacity limit",
        asset_types=["transmission_line"],
        category=FaultCategory.THERMAL, severity=FaultSeverity.HIGH,
        description="Conductor temperature exceeding 85°C (ACSR aluminum limit). Annealing and permanent sag risk.",
        detection_method="threshold",
        threshold_param="conductor_temp_c", threshold_hi=85.0,
        recommended_action="Reduce loading to below dynamic rating. Schedule tension inspection.",
        nerc_standard="NERC FAC-008",
    ),

    # ── SMART METER / AMI ────────────────────────────────────────────────────
    FaultSignature(
        fault_code="AMI-001", name="Energy theft — consumption anomaly",
        asset_types=["smart_meter"],
        category=FaultCategory.SECURITY, severity=FaultSeverity.HIGH,
        description="Meter shows bypassing signature: low/zero consumption during high-demand period, or reverse flow without solar.",
        detection_method="ml_anomaly",
        threshold_param="consumption_anomaly_score", threshold_hi=0.85,
        recommended_action="Field inspection. Check meter seal integrity. Cross-reference with billing complaints.",
    ),
    FaultSignature(
        fault_code="AMI-002", name="Meter communication loss > 24h",
        asset_types=["smart_meter"],
        category=FaultCategory.COMMUNICATION, severity=FaultSeverity.LOW,
        description="AMI meter has not reported in >24 hours. Possible device fault, network outage, or physical damage.",
        detection_method="threshold",
        threshold_param="hours_since_last_reading", threshold_hi=24.0,
        recommended_action="Check network node. Attempt remote re-ping. Schedule field inspection if no response in 48h.",
    ),
    FaultSignature(
        fault_code="AMI-003", name="Phase imbalance — distribution fault",
        asset_types=["smart_meter", "substation"],
        category=FaultCategory.ELECTRICAL, severity=FaultSeverity.MEDIUM,
        description="Three-phase voltage imbalance >3% detected across meter cluster. Possible broken conductor or blown fuse.",
        detection_method="threshold",
        threshold_param="voltage_imbalance_pct", threshold_hi=3.0,
        recommended_action="Inspect distribution transformer and phase conductors in affected area.",
    ),
]

# ── Index by asset type ───────────────────────────────────────────────────────

def get_signatures_for_asset_type(asset_type: str) -> List[FaultSignature]:
    return [s for s in FAULT_SIGNATURES if asset_type in s.asset_types]

def get_signature_by_code(code: str) -> Optional[FaultSignature]:
    return next((s for s in FAULT_SIGNATURES if s.fault_code == code), None)

ALL_ASSET_TYPES = [
    "hydro_plant", "dam", "solar_farm", "wind_farm",
    "gas_peaker", "thermal_plant", "bess",
    "transmission_line", "substation", "smart_meter",
    "transformer", "circuit_breaker",
]
