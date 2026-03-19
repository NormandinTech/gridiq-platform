"""
GridIQ — Pydantic Schemas (API request/response models)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ── Base ──────────────────────────────────────────────────────────────────────

class GridIQBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# ── Asset schemas ─────────────────────────────────────────────────────────────

class AssetBase(GridIQBase):
    name: str
    asset_tag: str
    asset_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rated_capacity_mw: Optional[float] = None
    rated_voltage_kv: Optional[float] = None
    is_critical: bool = False


class AssetCreate(AssetBase):
    zone_id: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    protocol: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None


class AssetResponse(AssetBase):
    id: str
    zone_id: Optional[str] = None
    status: str
    health_score: float
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AssetHealthDetail(GridIQBase):
    asset_id: str
    asset_name: str
    health_score: float
    status: str
    last_seen: Optional[datetime]
    failure_probability_30d: Optional[float] = None
    next_maintenance: Optional[datetime] = None
    active_alerts: int = 0
    recent_anomalies: int = 0
    telemetry_summary: Dict[str, Any] = {}


# ── Telemetry schemas ────────────────────────────────────────────────────────

class TelemetryReadingResponse(GridIQBase):
    id: str
    asset_id: str
    timestamp: datetime
    active_power_mw: Optional[float] = None
    reactive_power_mvar: Optional[float] = None
    voltage_kv: Optional[float] = None
    current_amps: Optional[float] = None
    frequency_hz: Optional[float] = None
    temperature_c: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None


class LiveTelemetryEvent(BaseModel):
    """Pushed over WebSocket to connected dashboards."""
    event: str = "telemetry"
    asset_id: str
    asset_name: str
    asset_type: str
    timestamp: datetime
    readings: Dict[str, Any]


# ── Grid KPI schemas ──────────────────────────────────────────────────────────

class GridKPIs(BaseModel):
    timestamp: datetime
    total_load_mw: float
    total_generation_mw: float
    renewable_mw: float
    renewable_pct: float
    frequency_hz: float
    transmission_capacity_used_pct: float
    voltage_stability_index: float
    co2_intensity_g_kwh: float
    co2_avoided_tonnes_today: float
    system_inertia_pct: float
    active_alerts: int
    assets_online: int
    assets_total: int


class EnergyMix(BaseModel):
    solar_mw: float
    wind_mw: float
    hydro_mw: float
    gas_mw: float
    nuclear_mw: float = 0.0
    import_mw: float
    bess_charging_mw: float
    bess_discharging_mw: float
    total_mw: float
    renewable_pct: float


# ── Forecast schemas ─────────────────────────────────────────────────────────

class ForecastPoint(BaseModel):
    timestamp: datetime
    value_mw: float
    lower_ci_mw: Optional[float] = None
    upper_ci_mw: Optional[float] = None
    confidence: Optional[float] = None


class ForecastResponse(BaseModel):
    forecast_type: str
    generated_at: datetime
    model_version: str
    horizon_hours: int
    points: List[ForecastPoint]
    summary: Dict[str, Any] = {}


class RenewableForecastHour(BaseModel):
    hour_offset: int
    timestamp: datetime
    solar_mw: float
    wind_mw: float
    total_renewable_mw: float
    status: str  # on_target | wind_drop | peak_risk | reserve_low | recovering
    note: Optional[str] = None


# ── Alert schemas ─────────────────────────────────────────────────────────────

class AlertResponse(GridIQBase):
    id: str
    asset_id: Optional[str] = None
    severity: str
    status: str
    title: str
    description: Optional[str] = None
    source: str
    category: str
    confidence: Optional[float] = None
    recommended_action: Optional[str] = None
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class AlertAcknowledge(BaseModel):
    acknowledged_by: str
    note: Optional[str] = None


class AlertCreate(BaseModel):
    asset_id: Optional[str] = None
    zone_id: Optional[str] = None
    severity: str
    title: str
    description: Optional[str] = None
    source: str = "manual"
    category: str = "operational"
    recommended_action: Optional[str] = None


# ── Maintenance schemas ───────────────────────────────────────────────────────

class MaintenanceResponse(GridIQBase):
    id: str
    asset_id: str
    asset_name: Optional[str] = None
    maintenance_type: str
    priority: str
    title: str
    description: Optional[str] = None
    predicted_failure_date: Optional[datetime] = None
    failure_probability: Optional[float] = None
    scheduled_date: Optional[datetime] = None
    status: str
    created_at: datetime


# ── Security / threat schemas ─────────────────────────────────────────────────

class ThreatResponse(GridIQBase):
    id: str
    asset_id: Optional[str] = None
    threat_level: str
    network_zone: Optional[str] = None
    title: str
    description: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    protocol: Optional[str] = None
    cve_id: Optional[str] = None
    attack_type: Optional[str] = None
    threat_score: Optional[float] = None
    is_blocked: bool
    is_active: bool
    incident_ticket: Optional[str] = None
    detected_at: datetime


class SecurityPosture(BaseModel):
    overall_score: int  # 0–100
    network_segmentation_score: int
    patch_compliance_score: int
    access_control_score: int
    endpoint_hardening_score: int
    active_threats: int
    events_today: int
    blocked_today: int
    mean_time_to_detect_min: float


class ZoneStatus(BaseModel):
    zone_name: str
    zone_code: str
    network_zone: str
    status: str  # secure | warning | critical
    active_threats: int
    device_count: int
    details: str


# ── Compliance schemas ────────────────────────────────────────────────────────

class ComplianceControlResponse(GridIQBase):
    id: str
    standard: str
    control_id: str
    title: str
    description: Optional[str] = None
    compliance_pct: float
    status: str
    last_assessed: Optional[datetime] = None
    due_date: Optional[datetime] = None
    findings: Optional[str] = None


class ComplianceSummary(BaseModel):
    overall_score: float
    compliant_controls: int
    total_controls: int
    critical_gaps: List[str]
    next_audit_days: int
    standards: Dict[str, float]  # standard -> avg compliance %


# ── WebSocket message schemas ─────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Auth schemas ──────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: List[str] = []


class LoginRequest(BaseModel):
    username: str
    password: str


# ── Paginated response ────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
