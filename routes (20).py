"""
GridIQ — Database Models (SQLAlchemy 2.0)
All platform entities: grid assets, telemetry, alerts, forecasts, threats, compliance.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


# ── Enumerations ──────────────────────────────────────────────────────────────

class AssetType(str, enum.Enum):
    TRANSFORMER       = "transformer"
    CIRCUIT_BREAKER   = "circuit_breaker"
    SWITCH            = "switch"
    CAPACITOR_BANK    = "capacitor_bank"
    RTU               = "rtu"
    SCADA_SERVER      = "scada_server"
    SOLAR_FARM        = "solar_farm"
    WIND_FARM         = "wind_farm"
    HYDRO_PLANT       = "hydro_plant"
    GAS_PEAKER        = "gas_peaker"
    BESS              = "bess"          # Battery Energy Storage System
    SUBSTATION        = "substation"
    TRANSMISSION_LINE = "transmission_line"
    SMART_METER       = "smart_meter"
    EV_CHARGER        = "ev_charger"


class AssetStatus(str, enum.Enum):
    ONLINE    = "online"
    OFFLINE   = "offline"
    DEGRADED  = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN   = "unknown"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class AlertStatus(str, enum.Enum):
    OPEN         = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED     = "resolved"
    SUPPRESSED   = "suppressed"


class ThreatLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class NetworkZone(str, enum.Enum):
    INTERNET  = "internet"
    DMZ       = "dmz"
    IT        = "it"
    OT        = "ot"
    AMI       = "ami"


# ── Core grid models ──────────────────────────────────────────────────────────

class GridZone(Base):
    """
    Geographic / operational zone (e.g. North Zone, Substation 7A).
    Assets belong to zones. Zones have health scores.
    """
    __tablename__ = "grid_zones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    voltage_kv: Mapped[Optional[float]] = mapped_column(Float)
    capacity_mw: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="zone")


class Asset(Base):
    """
    Physical grid asset — transformer, breaker, RTU, solar farm, etc.
    Central entity connecting telemetry, alerts, and maintenance.
    """
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    zone_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grid_zones.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.ONLINE)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    install_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rated_capacity_mw: Mapped[Optional[float]] = mapped_column(Float)
    rated_voltage_kv: Mapped[Optional[float]] = mapped_column(Float)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    # SCADA connection
    protocol: Mapped[Optional[str]] = mapped_column(String(50))   # modbus, dnp3, iec61850, mqtt
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    polling_interval_sec: Mapped[int] = mapped_column(Integer, default=30)
    # Health
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    nerc_cip_asset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    zone: Mapped[Optional["GridZone"]] = relationship("GridZone", back_populates="assets")
    telemetry: Mapped[List["TelemetryReading"]] = relationship("TelemetryReading", back_populates="asset")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="asset")
    maintenance_records: Mapped[List["MaintenanceRecord"]] = relationship("MaintenanceRecord", back_populates="asset")

    __table_args__ = (
        Index("ix_assets_zone_id", "zone_id"),
        Index("ix_assets_asset_type", "asset_type"),
        Index("ix_assets_status", "status"),
    )


# ── Telemetry (time-series) ────────────────────────────────────────────────────

class TelemetryReading(Base):
    """
    Raw sensor readings from assets.
    In production this table is a TimescaleDB hypertable — partitioned by time.
    CREATE INDEX ON telemetry_readings (asset_id, timestamp DESC);
    SELECT create_hypertable('telemetry_readings', 'timestamp');
    """
    __tablename__ = "telemetry_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    # Power measurements
    active_power_mw: Mapped[Optional[float]] = mapped_column(Float)
    reactive_power_mvar: Mapped[Optional[float]] = mapped_column(Float)
    apparent_power_mva: Mapped[Optional[float]] = mapped_column(Float)
    power_factor: Mapped[Optional[float]] = mapped_column(Float)
    # Voltage / current
    voltage_kv: Mapped[Optional[float]] = mapped_column(Float)
    current_amps: Mapped[Optional[float]] = mapped_column(Float)
    frequency_hz: Mapped[Optional[float]] = mapped_column(Float)
    # Thermal
    temperature_c: Mapped[Optional[float]] = mapped_column(Float)
    oil_temperature_c: Mapped[Optional[float]] = mapped_column(Float)
    # State
    status_raw: Mapped[Optional[str]] = mapped_column(String(50))
    # Catch-all for asset-specific readings
    extra: Mapped[Optional[dict]] = mapped_column(JSON)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="telemetry")

    __table_args__ = (
        Index("ix_telemetry_asset_ts", "asset_id", "timestamp"),
        Index("ix_telemetry_timestamp", "timestamp"),
    )


class GridSnapshot(Base):
    """
    Aggregate system-level snapshot every minute.
    Used for KPI dashboards and trend analysis.
    """
    __tablename__ = "grid_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    total_load_mw: Mapped[Optional[float]] = mapped_column(Float)
    total_generation_mw: Mapped[Optional[float]] = mapped_column(Float)
    renewable_mw: Mapped[Optional[float]] = mapped_column(Float)
    renewable_pct: Mapped[Optional[float]] = mapped_column(Float)
    frequency_hz: Mapped[Optional[float]] = mapped_column(Float)
    transmission_capacity_used_pct: Mapped[Optional[float]] = mapped_column(Float)
    voltage_stability_index: Mapped[Optional[float]] = mapped_column(Float)
    co2_intensity_g_kwh: Mapped[Optional[float]] = mapped_column(Float)
    co2_avoided_tonnes: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (Index("ix_grid_snapshots_timestamp", "timestamp"),)


# ── Alerts ────────────────────────────────────────────────────────────────────

class Alert(Base):
    """
    Operational and security alerts. Tied to an asset and zone.
    Source can be: AI anomaly detection, threshold breach, security IDS, manual.
    """
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("assets.id"))
    zone_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grid_zones.id"))
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.OPEN)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="system")  # ai | threshold | security | manual
    category: Mapped[str] = mapped_column(String(50), default="operational")  # operational | security | maintenance | compliance
    # AI metadata
    confidence: Mapped[Optional[float]] = mapped_column(Float)     # 0–1
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float)  # 0–100
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    asset: Mapped[Optional["Asset"]] = relationship("Asset", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_created_at", "created_at"),
    )


# ── Forecasts ────────────────────────────────────────────────────────────────

class ForecastRecord(Base):
    """
    AI-generated demand and renewable forecasts. Stored for accuracy tracking.
    """
    __tablename__ = "forecast_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    forecast_type: Mapped[str] = mapped_column(String(50))  # demand | solar | wind | renewable_total
    zone_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grid_zones.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    model_version: Mapped[str] = mapped_column(String(50), default="v1")
    horizon_hours: Mapped[int] = mapped_column(Integer, default=48)
    # Forecast data stored as JSON array of {timestamp, value, lower_ci, upper_ci}
    forecast_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Accuracy (filled in retrospectively)
    rmse_mw: Mapped[Optional[float]] = mapped_column(Float)
    mape_pct: Mapped[Optional[float]] = mapped_column(Float)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)


# ── Maintenance ───────────────────────────────────────────────────────────────

class MaintenanceRecord(Base):
    """
    Predictive and scheduled maintenance records per asset.
    AI generates predicted failure dates; operations schedules work orders.
    """
    __tablename__ = "maintenance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False)
    maintenance_type: Mapped[str] = mapped_column(String(100))  # predictive | scheduled | corrective
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # urgent | high | normal | low
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    # AI prediction
    predicted_failure_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failure_probability: Mapped[Optional[float]] = mapped_column(Float)  # 0–1
    # Scheduling
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100))
    work_order_id: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="open")  # open | scheduled | in_progress | completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="maintenance_records")


# ── Cybersecurity ─────────────────────────────────────────────────────────────

class SecurityThreat(Base):
    """
    OT/IT security threats detected by the IDS/anomaly engine.
    """
    __tablename__ = "security_threats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("assets.id"))
    threat_level: Mapped[ThreatLevel] = mapped_column(Enum(ThreatLevel), nullable=False)
    network_zone: Mapped[Optional[NetworkZone]] = mapped_column(Enum(NetworkZone))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))
    destination_ip: Mapped[Optional[str]] = mapped_column(String(45))
    protocol: Mapped[Optional[str]] = mapped_column(String(50))  # modbus, dnp3, tcp, etc.
    cve_id: Mapped[Optional[str]] = mapped_column(String(50))    # e.g. CVE-2024-3811
    attack_type: Mapped[Optional[str]] = mapped_column(String(100))
    threat_score: Mapped[Optional[float]] = mapped_column(Float)  # 0–100
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    incident_ticket: Mapped[Optional[str]] = mapped_column(String(100))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)


class AccessLog(Base):
    """
    Zero-trust access log — every access request recorded.
    Required for NERC CIP-007 compliance.
    """
    __tablename__ = "access_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user_id: Mapped[Optional[str]] = mapped_column(String(100))
    username: Mapped[Optional[str]] = mapped_column(String(100))
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))
    target_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("assets.id"))
    target_resource: Mapped[Optional[str]] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))  # login | read | write | command | config_change
    outcome: Mapped[str] = mapped_column(String(20))  # allow | deny | block
    mfa_used: Mapped[bool] = mapped_column(Boolean, default=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[dict]] = mapped_column(JSON)

    __table_args__ = (Index("ix_access_logs_timestamp", "timestamp"),)


# ── Compliance ────────────────────────────────────────────────────────────────

class ComplianceControl(Base):
    """
    NERC CIP compliance controls with current status.
    Updated by automated compliance checker service.
    """
    __tablename__ = "compliance_controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    standard: Mapped[str] = mapped_column(String(50))  # NERC_CIP | FERC | EPA | NIST
    control_id: Mapped[str] = mapped_column(String(50), nullable=False)  # CIP-007 etc.
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    compliance_pct: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="unknown")  # compliant | partial | non_compliant | unknown
    last_assessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    findings: Mapped[Optional[str]] = mapped_column(Text)
    remediation_plan: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("standard", "control_id", name="uq_compliance_standard_control"),)
