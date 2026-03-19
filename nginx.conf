"""
GridIQ Sensor Catalog
=====================
Complete catalog of sensors compatible with GridIQ.
Covers every sensor type needed across all energy asset types.

Each sensor definition includes:
  - Technical specifications
  - Supported communication protocols
  - Compatible asset types
  - Calibration requirements
  - Estimated cost ranges
  - Which GridIQ fault signatures it feeds
  - Recommended manufacturers

Sensor categories:
  ELECTRICAL   — voltage, current, power, power quality
  MECHANICAL   — vibration, rotation, torque, displacement
  THERMAL      — temperature (contact + non-contact)
  CHEMICAL     — dissolved gas, oil quality, emissions
  HYDRAULIC    — pressure, flow, level
  STRUCTURAL   — strain, tilt, seepage, displacement
  ENVIRONMENTAL— weather, irradiance, wind, ice
  OPTICAL      — camera, thermal imaging, LiDAR
  COMMUNICATION— signal quality, data integrity
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SensorCategory(str, Enum):
    ELECTRICAL    = "electrical"
    MECHANICAL    = "mechanical"
    THERMAL       = "thermal"
    CHEMICAL      = "chemical"
    HYDRAULIC     = "hydraulic"
    STRUCTURAL    = "structural"
    ENVIRONMENTAL = "environmental"
    OPTICAL       = "optical"
    COMMUNICATION = "communication"


class CalibrationFrequency(str, Enum):
    MONTHLY   = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL    = "annual"
    BIANNUAL  = "biannual"
    ON_DEMAND = "on_demand"


class DeploymentStatus(str, Enum):
    PLANNED    = "planned"
    ORDERED    = "ordered"
    INSTALLED  = "installed"
    CALIBRATED = "calibrated"
    ONLINE     = "online"
    DEGRADED   = "degraded"
    OFFLINE    = "offline"
    RETIRED    = "retired"


@dataclass
class SensorSpec:
    """
    Specification for a sensor type in the GridIQ catalog.
    This is the template — deployed sensors are instances of this spec.
    """
    sensor_type_id: str
    name: str
    category: SensorCategory
    description: str
    # Compatibility
    compatible_asset_types: List[str]
    feeds_fault_codes: List[str]       # which fault signatures this sensor enables
    # Technical specs
    measurement_parameter: str         # what it measures
    measurement_unit: str
    measurement_range_lo: Optional[float] = None
    measurement_range_hi: Optional[float] = None
    accuracy_pct: Optional[float] = None
    resolution: Optional[str] = None
    sample_rate_hz: Optional[float] = None   # samples per second
    # Connectivity
    protocols: List[str] = field(default_factory=list)   # modbus, mqtt, opc-ua, canbus, etc.
    power_requirement: str = "24VDC"
    ip_rating: str = "IP65"
    operating_temp_range: str = "-20°C to +70°C"
    # Calibration
    calibration_frequency: CalibrationFrequency = CalibrationFrequency.ANNUAL
    calibration_method: str = ""
    # Commercial
    cost_usd_lo: Optional[int] = None
    cost_usd_hi: Optional[int] = None
    install_cost_usd: Optional[int] = None
    lead_time_weeks: Optional[int] = None
    manufacturers: List[str] = field(default_factory=list)
    # ROI context
    roi_description: str = ""
    priority: str = "standard"   # critical | high | standard | optional


# ── SENSOR CATALOG ────────────────────────────────────────────────────────────

SENSOR_CATALOG: List[SensorSpec] = [

    # ════════════════════════════════════════════════════════════
    # ELECTRICAL SENSORS
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="EL-001",
        name="Revenue-grade power meter",
        category=SensorCategory.ELECTRICAL,
        description=(
            "ANSI C12.20 Class 0.2 accuracy. Measures active power, reactive power, "
            "apparent power, power factor, THD. 3-phase. Used at generation interconnection "
            "and substation feeder level."
        ),
        compatible_asset_types=["substation", "solar_farm", "wind_farm", "hydro_plant",
                                 "gas_peaker", "bess", "transformer"],
        feeds_fault_codes=["GEN-LOSS", "SOL-003", "WND-005", "HYD-004"],
        measurement_parameter="Active/reactive power, voltage, current, PF, THD",
        measurement_unit="kW, kVAR, V, A, %",
        accuracy_pct=0.2,
        sample_rate_hz=60.0,
        protocols=["modbus_tcp", "dnp3", "iec61850", "opc_ua"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="NIST-traceable current injection, known burden",
        cost_usd_lo=800, cost_usd_hi=4000,
        install_cost_usd=500,
        lead_time_weeks=4,
        manufacturers=["Schneider Electric PM8000", "ABB M4M", "Siemens SENTRON PAC",
                        "GE PowerLogic ION9000", "Eaton IQ250"],
        roi_description="Foundation sensor — enables all energy loss calculations",
        priority="critical",
    ),

    SensorSpec(
        sensor_type_id="EL-002",
        name="DC string current monitor",
        category=SensorCategory.ELECTRICAL,
        description=(
            "Monitors individual DC string current at the combiner box level in solar farms. "
            "Enables string-level fault detection (open circuit, partial shading, degradation). "
            "Most solar farms only monitor at inverter level — this adds 20× more resolution."
        ),
        compatible_asset_types=["solar_farm"],
        feeds_fault_codes=["SOL-001", "SOL-006"],
        measurement_parameter="DC string current",
        measurement_unit="A",
        measurement_range_lo=0.0, measurement_range_hi=20.0,
        accuracy_pct=0.5,
        sample_rate_hz=1.0,
        protocols=["modbus_rtu", "rs485", "mqtt"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="Clamp ammeter comparison",
        cost_usd_lo=50, cost_usd_hi=200,
        install_cost_usd=80,
        lead_time_weeks=2,
        manufacturers=["IMO Precision Controls", "Raychem nVent", "Solar-Log",
                        "SMA Sunny Sensor Box", "Tigo Energy"],
        roi_description=(
            "A single failed string on a 300MW farm costs ~$500/day. "
            "String monitoring finds it within 15 minutes vs weeks."
        ),
        priority="critical",
    ),

    SensorSpec(
        sensor_type_id="EL-003",
        name="Partial discharge monitor (HFCT)",
        category=SensorCategory.ELECTRICAL,
        description=(
            "High-Frequency Current Transformer permanently installed on cable terminations, "
            "transformer bushings, and GIS. Detects partial discharge activity indicating "
            "insulation degradation. Can predict failure 6–18 months in advance."
        ),
        compatible_asset_types=["transformer", "substation", "transmission_line"],
        feeds_fault_codes=["TXN-002"],
        measurement_parameter="Partial discharge magnitude",
        measurement_unit="pC (picocoulombs)",
        measurement_range_lo=0.0, measurement_range_hi=10000.0,
        accuracy_pct=5.0,
        sample_rate_hz=1000000.0,
        protocols=["modbus_tcp", "iec61850", "industrial_ethernet"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="IEC 60270 calibration injector",
        cost_usd_lo=500, cost_usd_hi=2000,
        install_cost_usd=800,
        lead_time_weeks=6,
        manufacturers=["Doble Engineering", "Megger", "Qualitrol", "IPEC", "Omicron"],
        roi_description=(
            "One prevented transformer failure saves $500K–$5M in equipment + outage costs. "
            "A $2K sensor protecting a $2M transformer is a 1000:1 ROI."
        ),
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="EL-004",
        name="Power quality analyzer",
        category=SensorCategory.ELECTRICAL,
        description=(
            "Continuous monitoring of voltage sags, swells, flicker, harmonics, "
            "transients, and interruptions per IEC 61000-4-30 Class A. "
            "Critical at grid interconnection points and sensitive industrial loads."
        ),
        compatible_asset_types=["substation", "smart_meter", "transformer"],
        feeds_fault_codes=["AMI-003", "TXN-002"],
        measurement_parameter="Voltage/current waveform, PQ events",
        measurement_unit="V, A, Hz, %, events",
        sample_rate_hz=12800.0,
        protocols=["modbus_tcp", "iec61850", "dnp3"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=2000, cost_usd_hi=8000,
        lead_time_weeks=4,
        manufacturers=["Fluke 1760", "Dranetz HDPQ", "Elspec G4500",
                        "Schneider ION9000", "ABB PQS"],
        priority="standard",
    ),

    SensorSpec(
        sensor_type_id="EL-005",
        name="Cell voltage + temperature BMS tap",
        category=SensorCategory.ELECTRICAL,
        description=(
            "CAN bus or Modbus interface to battery management system. "
            "Exposes individual cell voltages (mV resolution), temperatures, "
            "state of charge, state of health, and cycle count per module. "
            "Often requires manufacturer API agreement."
        ),
        compatible_asset_types=["bess"],
        feeds_fault_codes=["BSS-001", "BSS-002", "BSS-003", "BSS-004"],
        measurement_parameter="Cell voltage, temperature, SOC, SOH",
        measurement_unit="mV, °C, %, cycles",
        accuracy_pct=0.1,
        sample_rate_hz=10.0,
        protocols=["canbus", "modbus_tcp", "rest_api", "opc_ua"],
        calibration_frequency=CalibrationFrequency.BIANNUAL,
        calibration_method="Known reference voltage + calibrated thermocouple",
        cost_usd_lo=5000, cost_usd_hi=20000,
        install_cost_usd=2000,
        lead_time_weeks=8,
        manufacturers=["Tesla Megapack API", "Fluence Edgware", "BYD BMS",
                        "Wärtsilä GEMS", "CATL BMS"],
        roi_description=(
            "Thermal runaway in a BESS can destroy a $50M system. "
            "BSS-001 detection with <30s response prevents total loss."
        ),
        priority="critical",
    ),


    # ════════════════════════════════════════════════════════════
    # MECHANICAL SENSORS
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="ME-001",
        name="Industrial vibration sensor (triaxial MEMS)",
        category=SensorCategory.MECHANICAL,
        description=(
            "Triaxial MEMS accelerometer for continuous vibration monitoring on rotating "
            "machinery. Measures RMS, peak, and frequency spectrum. Detects bearing faults "
            "(BPFO/BPFI signatures), imbalance (1P), misalignment (2P), and looseness. "
            "Critical for wind turbine gearboxes and hydro turbines."
        ),
        compatible_asset_types=["wind_farm", "hydro_plant", "gas_peaker"],
        feeds_fault_codes=["HYD-001", "WND-001", "WND-002", "GAS-003"],
        measurement_parameter="Acceleration (triaxial), velocity, displacement",
        measurement_unit="g, mm/s, μm",
        measurement_range_lo=-16.0, measurement_range_hi=16.0,
        accuracy_pct=1.0,
        sample_rate_hz=25600.0,
        protocols=["modbus_tcp", "mqtt", "industrial_ethernet", "ble"],
        ip_rating="IP67",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="ISO 16063-21 back-to-back calibration",
        cost_usd_lo=200, cost_usd_hi=800,
        install_cost_usd=200,
        lead_time_weeks=3,
        manufacturers=["SKF CMSS 793", "ifm Electronic VSA001",
                        "Brüel & Kjær Type 4514", "PCB Piezotronics 356B18",
                        "Emerson CSI 9420"],
        roi_description=(
            "Wind gearbox replacement costs $200–400K + 2 weeks downtime. "
            "A $500 sensor detecting failure 4 weeks early saves 80% of that cost."
        ),
        priority="critical",
    ),

    SensorSpec(
        sensor_type_id="ME-002",
        name="Blade root load cell (wind)",
        category=SensorCategory.MECHANICAL,
        description=(
            "Strain gauge load cell at blade root measuring flapwise and edgewise bending. "
            "Detects aerodynamic imbalance, ice loading, and pitch system faults. "
            "Also used for fatigue lifetime estimation."
        ),
        compatible_asset_types=["wind_farm"],
        feeds_fault_codes=["WND-002", "WND-006"],
        measurement_parameter="Bending moment (flapwise + edgewise)",
        measurement_unit="kNm",
        accuracy_pct=0.5,
        sample_rate_hz=100.0,
        protocols=["slip_ring_analog", "wireless_strain", "opc_ua"],
        ip_rating="IP68",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=3000, cost_usd_hi=8000,
        install_cost_usd=5000,
        lead_time_weeks=10,
        manufacturers=["HBK (Hottinger Baldwin)", "LM Wind Power", "Vestas OEM",
                        "Mita-Teknik", "Strainsert"],
        priority="standard",
    ),

    SensorSpec(
        sensor_type_id="ME-003",
        name="Shaft encoder / tachometer",
        category=SensorCategory.MECHANICAL,
        description=(
            "Optical or magnetic rotational speed sensor. Provides exact RPM and "
            "shaft position for phase-resolved vibration analysis, slip calculation, "
            "and power curve verification."
        ),
        compatible_asset_types=["wind_farm", "hydro_plant", "gas_peaker"],
        feeds_fault_codes=["WND-001", "WND-003", "WND-005", "HYD-001"],
        measurement_parameter="Rotational speed, shaft position",
        measurement_unit="RPM, °",
        accuracy_pct=0.01,
        sample_rate_hz=10000.0,
        protocols=["htl_pulse", "modbus_rtu", "ssi"],
        cost_usd_lo=150, cost_usd_hi=600,
        install_cost_usd=300,
        lead_time_weeks=2,
        manufacturers=["Heidenhain", "Sick AG", "Pepperl+Fuchs", "Baumer", "Kübler"],
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="ME-004",
        name="Penstock pressure transducer",
        category=SensorCategory.HYDRAULIC,
        description=(
            "Differential pressure transducer measuring head loss across penstock sections. "
            "Detects obstruction, corrosion buildup, and valve leakage in hydro penstocks."
        ),
        compatible_asset_types=["hydro_plant", "dam"],
        feeds_fault_codes=["HYD-002"],
        measurement_parameter="Differential pressure",
        measurement_unit="bar, PSI",
        measurement_range_lo=0.0, measurement_range_hi=100.0,
        accuracy_pct=0.1,
        sample_rate_hz=10.0,
        protocols=["4_20ma", "hart", "modbus_rtu"],
        ip_rating="IP68",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="Dead-weight tester comparison",
        cost_usd_lo=300, cost_usd_hi=1200,
        install_cost_usd=800,
        manufacturers=["Rosemount 3051", "Yokogawa EJA", "Endress+Hauser PMD75",
                        "Vega VEGABAR"],
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="ME-005",
        name="Conductor sag / tension monitor",
        category=SensorCategory.MECHANICAL,
        description=(
            "Real-time conductor sag monitoring via inclinometer on the conductor "
            "or tension load cell at the dead-end tower. Combined with weather data "
            "enables dynamic line rating — typically 20–40% more throughput."
        ),
        compatible_asset_types=["transmission_line"],
        feeds_fault_codes=["TXN-001", "TXN-003"],
        measurement_parameter="Conductor tension / sag angle",
        measurement_unit="kN, degrees",
        accuracy_pct=0.5,
        protocols=["gsm_4g", "rf_mesh", "satellite"],
        ip_rating="IP67",
        calibration_frequency=CalibrationFrequency.BIANNUAL,
        cost_usd_lo=5000, cost_usd_hi=15000,
        install_cost_usd=3000,
        lead_time_weeks=8,
        manufacturers=["Lindsey Systems", "Ampacimon", "OPT EDX",
                        "Nexans NetSense", "SensorTran"],
        roi_description=(
            "Dynamic line rating on a congested 230kV line can add $2–8M/yr "
            "in transmission revenue without building new wire."
        ),
        priority="high",
    ),


    # ════════════════════════════════════════════════════════════
    # THERMAL SENSORS
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="TH-001",
        name="Transformer winding temperature (fiber optic)",
        category=SensorCategory.THERMAL,
        description=(
            "Fiber optic distributed temperature sensing (DTS) embedded in transformer "
            "winding during manufacture or retrofitted at rewind. Gives direct hot-spot "
            "temperature rather than calculated estimate. IEC 60076-7 compliant."
        ),
        compatible_asset_types=["transformer"],
        feeds_fault_codes=["TXN-003"],
        measurement_parameter="Winding hot-spot temperature",
        measurement_unit="°C",
        measurement_range_lo=-40.0, measurement_range_hi=200.0,
        accuracy_pct=1.0,
        sample_rate_hz=0.1,
        protocols=["modbus_tcp", "iec61850"],
        calibration_frequency=CalibrationFrequency.BIANNUAL,
        cost_usd_lo=5000, cost_usd_hi=15000,
        lead_time_weeks=12,
        manufacturers=["Neoptix", "Luna Innovations", "Yokogawa",
                        "AP Sensing", "Sensornet"],
        roi_description=(
            "Every 8°C above rated temperature halves transformer insulation life. "
            "Accurate hot-spot data allows 15% more loading with same risk profile."
        ),
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="TH-002",
        name="Thermal imaging camera (fixed mount)",
        category=SensorCategory.OPTICAL,
        description=(
            "Fixed mount uncooled microbolometer thermal camera for continuous "
            "monitoring of switchgear, busbar connections, cable terminations. "
            "Detects loose connections, overloaded components, and arc flash precursors."
        ),
        compatible_asset_types=["substation", "transformer", "solar_farm"],
        feeds_fault_codes=["SOL-002", "TXN-002"],
        measurement_parameter="Surface temperature (radiometric)",
        measurement_unit="°C",
        measurement_range_lo=-20.0, measurement_range_hi=2000.0,
        accuracy_pct=2.0,
        sample_rate_hz=9.0,
        protocols=["ethernet", "rtsp_stream", "modbus_tcp"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=3000, cost_usd_hi=12000,
        install_cost_usd=1500,
        lead_time_weeks=6,
        manufacturers=["FLIR A700", "Axis Q1942-E", "Hikvision DS-2TD",
                        "Optris PI", "InfraTec ImageIR"],
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="TH-003",
        name="RTD / thermocouple array (generator/turbine)",
        category=SensorCategory.THERMAL,
        description=(
            "PT100 RTD or Type K thermocouple arrays monitoring generator stator windings, "
            "bearing housings, cooling air inlet/outlet. 12–48 measurement points per unit."
        ),
        compatible_asset_types=["wind_farm", "hydro_plant", "gas_peaker"],
        feeds_fault_codes=["WND-004", "GAS-002", "HYD-001"],
        measurement_parameter="Temperature (multiple points)",
        measurement_unit="°C",
        measurement_range_lo=-50.0, measurement_range_hi=250.0,
        accuracy_pct=0.3,
        sample_rate_hz=1.0,
        protocols=["4_20ma", "modbus_rtu", "pt100_direct"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="Dry block calibrator comparison",
        cost_usd_lo=50, cost_usd_hi=300,
        install_cost_usd=150,
        lead_time_weeks=2,
        manufacturers=["Pt100 generic", "Omega Engineering", "TC Direct",
                        "Endress+Hauser", "Wika"],
        priority="standard",
    ),


    # ════════════════════════════════════════════════════════════
    # CHEMICAL SENSORS
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="CH-001",
        name="Continuous dissolved gas analyzer (DGA)",
        category=SensorCategory.CHEMICAL,
        description=(
            "Online transformer oil DGA monitor measuring H2, CH4, C2H2, C2H4, C2H6, CO, CO2. "
            "Replaces manual oil sampling (1-2x/year) with continuous monitoring. "
            "Different gas ratios identify specific fault types: "
            "acetylene = arcing, ethylene = overheating, hydrogen = partial discharge."
        ),
        compatible_asset_types=["transformer"],
        feeds_fault_codes=["TRF-DGA-001"],
        measurement_parameter="Dissolved gas concentrations in transformer oil",
        measurement_unit="ppm",
        measurement_range_lo=0.0, measurement_range_hi=10000.0,
        accuracy_pct=5.0,
        sample_rate_hz=0.00028,   # Once per hour
        protocols=["modbus_tcp", "iec61850", "dnp3"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="Certified gas reference standard",
        cost_usd_lo=8000, cost_usd_hi=25000,
        install_cost_usd=2000,
        lead_time_weeks=12,
        manufacturers=["GE Kelman TRANSFIX", "Vaisala OPT100",
                        "Qualitrol 509", "Morgan Schaffer Calisto",
                        "Serveron TM8"],
        roi_description=(
            "Average transformer failure costs $500K–$5M equipment + 6-week lead time replacement. "
            "DGA detects developing faults 3–6 months early with 85%+ accuracy."
        ),
        priority="critical",
    ),

    SensorSpec(
        sensor_type_id="CH-002",
        name="NOx / emissions CEMS",
        category=SensorCategory.CHEMICAL,
        description=(
            "Continuous Emissions Monitoring System for NOx, SO2, CO, O2, PM. "
            "EPA 40 CFR Part 60/75 compliance. Required by permit for gas peakers. "
            "Real-time data to GridIQ prevents permit exceedances and USEPA fines."
        ),
        compatible_asset_types=["gas_peaker", "thermal_plant"],
        feeds_fault_codes=["GAS-004"],
        measurement_parameter="NOx, SO2, CO, O2, PM concentrations",
        measurement_unit="ppm, mg/Nm³, lb/MMBtu",
        accuracy_pct=2.0,
        protocols=["modbus_tcp", "4_20ma", "epa_electronic_reporting"],
        calibration_frequency=CalibrationFrequency.QUARTERLY,
        calibration_method="EPA Protocol Gas certified cylinder",
        cost_usd_lo=30000, cost_usd_hi=80000,
        install_cost_usd=20000,
        lead_time_weeks=16,
        manufacturers=["AMETEK Land", "Siemens OXYMAT", "ABB ACF5000",
                        "Emerson X-STREAM", "Thermo Scientific 42i"],
        roi_description=(
            "Single NOx permit exceedance fine: $10K–$100K per day. "
            "CEMS integration prevents violations and automates EPA reporting."
        ),
        priority="high",
    ),


    # ════════════════════════════════════════════════════════════
    # HYDRAULIC SENSORS
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="HY-001",
        name="Reservoir level sensor (radar)",
        category=SensorCategory.HYDRAULIC,
        description=(
            "Non-contact radar level transmitter for reservoir and forebay monitoring. "
            "Weather-proof, no moving parts. Used for water management, drought forecasting, "
            "and generation scheduling."
        ),
        compatible_asset_types=["dam", "hydro_plant"],
        feeds_fault_codes=["HYD-006"],
        measurement_parameter="Water surface elevation",
        measurement_unit="m, ft",
        measurement_range_lo=0.0, measurement_range_hi=70.0,
        accuracy_pct=0.1,
        protocols=["4_20ma", "hart", "modbus_rtu", "sdi_12"],
        ip_rating="IP68",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=1500, cost_usd_hi=5000,
        install_cost_usd=1000,
        manufacturers=["Vega VEGAPULS", "Endress+Hauser FMR",
                        "Rosemount 3300", "Siemens Sitrans LR250"],
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="HY-002",
        name="Dam seepage / piezometer (automated)",
        category=SensorCategory.STRUCTURAL,
        description=(
            "Vibrating wire piezometer or standpipe piezometer with automated readout. "
            "Measures pore water pressure in dam embankment and foundation. "
            "Critical FERC Part 12 safety instrument. Most dams read these manually — "
            "automation enables 15-minute reporting and trend alerts."
        ),
        compatible_asset_types=["dam"],
        feeds_fault_codes=["HYD-003"],
        measurement_parameter="Pore water pressure / seepage flow",
        measurement_unit="kPa, L/s",
        accuracy_pct=0.1,
        protocols=["vibrating_wire", "sdi_12", "modbus_rtu"],
        ip_rating="IP68",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=300, cost_usd_hi=1500,
        install_cost_usd=500,
        lead_time_weeks=4,
        manufacturers=["Campbell Scientific", "In-Situ", "RST Instruments",
                        "Slope Indicator", "Geosense"],
        roi_description=(
            "Dam failure liability: catastrophic. FERC requires dam safety instrumentation. "
            "Automating manual readings removes human error and enables 24/7 alerting."
        ),
        priority="critical",
    ),

    SensorSpec(
        sensor_type_id="HY-003",
        name="Water flow meter (ultrasonic clamp-on)",
        category=SensorCategory.HYDRAULIC,
        description=(
            "Clamp-on transit-time ultrasonic flow meter. Non-invasive — no pipe penetration. "
            "Measures actual water flow through penstock for real-time power output verification "
            "and hydro plant efficiency calculation."
        ),
        compatible_asset_types=["hydro_plant", "dam"],
        feeds_fault_codes=["HYD-002", "HYD-004"],
        measurement_parameter="Volumetric flow rate",
        measurement_unit="m³/s, m³/h",
        accuracy_pct=1.0,
        protocols=["modbus_rtu", "4_20ma", "hart"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=3000, cost_usd_hi=12000,
        install_cost_usd=2000,
        lead_time_weeks=6,
        manufacturers=["FLEXIM FLUXUS", "Siemens SITRANS FS", "GE Panametrics",
                        "Endress+Hauser Proline", "KROHNE OPTISONIC"],
        priority="high",
    ),


    # ════════════════════════════════════════════════════════════
    # ENVIRONMENTAL / WEATHER
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="EN-001",
        name="Solar irradiance station (Class A)",
        category=SensorCategory.ENVIRONMENTAL,
        description=(
            "ISO 9060 Class A silicon pyranometer for global horizontal irradiance (GHI). "
            "Often paired with diffuse and direct normal irradiance sensors and a "
            "reference cell for soiling ratio calculation. "
            "Essential for performance ratio calculation and soiling loss detection."
        ),
        compatible_asset_types=["solar_farm"],
        feeds_fault_codes=["SOL-002", "SOL-003", "SOL-006", "GEN-LOSS"],
        measurement_parameter="Solar irradiance (GHI, DNI, DHI)",
        measurement_unit="W/m²",
        measurement_range_lo=0.0, measurement_range_hi=1500.0,
        accuracy_pct=2.0,
        sample_rate_hz=1.0,
        protocols=["modbus_rtu", "4_20ma", "sdi_12"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="WRR (World Radiation Reference) comparison",
        cost_usd_lo=500, cost_usd_hi=3000,
        install_cost_usd=400,
        lead_time_weeks=4,
        manufacturers=["Kipp & Zonen CMP11", "EKO MS-80", "Hukseflux SR20",
                        "Li-COR LI-200R", "Apogee SP-510"],
        priority="critical",
    ),

    SensorSpec(
        sensor_type_id="EN-002",
        name="Wind measurement system (met mast / LiDAR)",
        category=SensorCategory.ENVIRONMENTAL,
        description=(
            "Cup anemometers + wind vanes at hub height, or vertical profiling LiDAR. "
            "Required for power curve verification, turbine yaw alignment, "
            "and wind resource assessment. LiDAR covers multiple heights without a tall mast."
        ),
        compatible_asset_types=["wind_farm"],
        feeds_fault_codes=["WND-003", "WND-005", "WND-006"],
        measurement_parameter="Wind speed, direction, turbulence intensity",
        measurement_unit="m/s, °, %",
        measurement_range_lo=0.0, measurement_range_hi=80.0,
        accuracy_pct=1.5,
        sample_rate_hz=1.0,
        protocols=["modbus_rtu", "4_20ma", "sdi_12", "opc_ua"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        calibration_method="MEASNET anemometer calibration",
        cost_usd_lo=10000, cost_usd_hi=200000,
        install_cost_usd=15000,
        lead_time_weeks=12,
        manufacturers=["Vaisala WXT530", "NRG Systems #40C", "Leosphere WindCube",
                        "ZX Lidars ZX 300", "Windar Photonics"],
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="EN-003",
        name="Ice detection system (wind turbine)",
        category=SensorCategory.ENVIRONMENTAL,
        description=(
            "Ultrasonic or capacitive ice sensor on nacelle or blade. Detects ice accretion "
            "before it causes imbalance or safety hazard. Works with blade heating system "
            "to activate deicing at right threshold."
        ),
        compatible_asset_types=["wind_farm"],
        feeds_fault_codes=["WND-006"],
        measurement_parameter="Ice presence / thickness",
        measurement_unit="mm, boolean",
        protocols=["modbus_rtu", "digital_io"],
        ip_rating="IP67",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=2000, cost_usd_hi=6000,
        install_cost_usd=1500,
        lead_time_weeks=8,
        manufacturers=["Labkotec LID-3300IP", "Combitech WISE",
                        "Boschung MARWIS-UMB", "Thyacon"],
        priority="standard",
    ),


    # ════════════════════════════════════════════════════════════
    # STRUCTURAL SENSORS
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="ST-001",
        name="Inclinometer / tilt sensor (tower + dam)",
        category=SensorCategory.STRUCTURAL,
        description=(
            "MEMS inclinometer measuring structure tilt in two axes. "
            "Used on wind turbine towers (foundation settlement), transmission towers "
            "(storm loading), and dam crests (deformation monitoring). "
            "Long-term trend analysis detects progressive settlement."
        ),
        compatible_asset_types=["wind_farm", "dam", "transmission_line"],
        feeds_fault_codes=["HYD-003", "TXN-001"],
        measurement_parameter="Inclination angle (biaxial)",
        measurement_unit="degrees, mrad",
        measurement_range_lo=-30.0, measurement_range_hi=30.0,
        accuracy_pct=0.01,
        sample_rate_hz=1.0,
        protocols=["modbus_rtu", "rs485", "4_20ma"],
        ip_rating="IP67",
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=200, cost_usd_hi=1200,
        install_cost_usd=300,
        manufacturers=["Pewatron", "TE Connectivity", "Measurement Specialties",
                        "RST Instruments", "Geokon"],
        priority="standard",
    ),

    SensorSpec(
        sensor_type_id="ST-002",
        name="Fiber optic distributed temperature / strain (DTS/DSS)",
        category=SensorCategory.STRUCTURAL,
        description=(
            "Single-mode fiber optic cable deployed along dam seepage collection galleries, "
            "or along transmission cables. Measures temperature and strain at every meter "
            "along the fiber length. Detects seepage hot spots and cable overload zones."
        ),
        compatible_asset_types=["dam", "transmission_line", "substation"],
        feeds_fault_codes=["HYD-003", "TXN-003"],
        measurement_parameter="Distributed temperature + strain",
        measurement_unit="°C, με (microstrain)",
        accuracy_pct=1.0,
        protocols=["industrial_ethernet", "modbus_tcp"],
        calibration_frequency=CalibrationFrequency.BIANNUAL,
        cost_usd_lo=20000, cost_usd_hi=80000,
        install_cost_usd=15000,
        lead_time_weeks=12,
        manufacturers=["AP Sensing", "Yokogawa DTSX", "Luna Innovations ODiSI",
                        "Sensornet Halo", "Schlumberger"],
        priority="standard",
    ),


    # ════════════════════════════════════════════════════════════
    # OPTICAL / IMAGING
    # ════════════════════════════════════════════════════════════

    SensorSpec(
        sensor_type_id="OP-001",
        name="Drone inspection system (thermal + RGB)",
        category=SensorCategory.OPTICAL,
        description=(
            "Autonomous or semi-autonomous drone platform with dual thermal + RGB camera. "
            "Used for: solar panel hotspot detection, wind blade LE erosion survey, "
            "transmission line corona/insulator inspection, vegetation encroachment mapping. "
            "Integrates inspection findings into GridIQ maintenance module."
        ),
        compatible_asset_types=["solar_farm", "wind_farm", "transmission_line",
                                  "substation", "dam"],
        feeds_fault_codes=["SOL-001", "SOL-002", "WND-002", "TXN-002"],
        measurement_parameter="Thermal + visual imagery",
        measurement_unit="°C, RGB pixels",
        protocols=["wifi", "4g_lte", "rest_api_upload"],
        calibration_frequency=CalibrationFrequency.ANNUAL,
        cost_usd_lo=15000, cost_usd_hi=80000,
        install_cost_usd=0,
        lead_time_weeks=8,
        manufacturers=["DJI M300 RTK", "Parrot ANAFI USA", "Percepto Arc",
                        "Skydio X2E", "Flyability ELIOS 3"],
        roi_description=(
            "Manual transmission line inspection: $2,000/mile. "
            "Drone inspection: $200/mile with thermal data. "
            "10× cost reduction + finds faults humans miss."
        ),
        priority="high",
    ),

    SensorSpec(
        sensor_type_id="OP-002",
        name="UV corona camera",
        category=SensorCategory.OPTICAL,
        description=(
            "Solar-blind UV camera sensitive to 240–280nm corona discharge on "
            "transmission line insulators, connectors, and transformer bushings. "
            "Detects corona that is invisible to the human eye and thermal cameras. "
            "Used for periodic inspection rather than continuous monitoring."
        ),
        compatible_asset_types=["transmission_line", "substation", "transformer"],
        feeds_fault_codes=["TXN-002"],
        measurement_parameter="UV photon count (corona discharge)",
        measurement_unit="photons/sec",
        protocols=["usb", "wifi", "bluetooth"],
        calibration_frequency=CalibrationFrequency.BIANNUAL,
        cost_usd_lo=8000, cost_usd_hi=25000,
        install_cost_usd=0,
        lead_time_weeks=4,
        manufacturers=["OFIL DayCor", "UViRCO CoroCAM", "Phenix Technologies",
                        "EPRI DayCorII"],
        priority="standard",
    ),
]


# ── Index helpers ─────────────────────────────────────────────────────────────

def get_sensors_for_asset_type(asset_type: str) -> List[SensorSpec]:
    return [s for s in SENSOR_CATALOG if asset_type in s.compatible_asset_types]


def get_sensors_for_fault_code(fault_code: str) -> List[SensorSpec]:
    return [s for s in SENSOR_CATALOG if fault_code in s.feeds_fault_codes]


def get_sensors_by_category(category: SensorCategory) -> List[SensorSpec]:
    return [s for s in SENSOR_CATALOG if s.category == category]


def get_critical_sensors() -> List[SensorSpec]:
    return [s for s in SENSOR_CATALOG if s.priority == "critical"]


def total_sensor_cost(sensor_type_ids: List[str], include_install: bool = True) -> Dict[str, int]:
    """Estimate total cost for a list of sensor types."""
    lo = hi = install = 0
    for sid in sensor_type_ids:
        spec = next((s for s in SENSOR_CATALOG if s.sensor_type_id == sid), None)
        if spec:
            lo += spec.cost_usd_lo or 0
            hi += spec.cost_usd_hi or 0
            if include_install:
                install += spec.install_cost_usd or 0
    return {"low": lo + install, "high": hi + install, "install_only": install}
