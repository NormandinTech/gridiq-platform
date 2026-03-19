"""
GridIQ — API Routes
Complete REST API: grid KPIs, assets, telemetry, forecasts, alerts,
maintenance, security threats, compliance, and WebSocket streams.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from backend.core.event_bus import EventType, emit, get_event_bus
from backend.ml.engine import (
    anomaly_detector, demand_forecaster, health_scorer,
    recommendation_engine, renewable_forecaster,
)
from backend.models.schemas import (
    AlertAcknowledge, AlertCreate, AlertResponse, AssetCreate,
    AssetHealthDetail, AssetResponse, ComplianceControlResponse,
    ComplianceSummary, ForecastResponse, GridKPIs, MaintenanceResponse,
    SecurityPosture, ThreatResponse, ZoneStatus,
)
from backend.security.cyber import compliance_checker, threat_engine, zero_trust

logger = logging.getLogger(__name__)
router = APIRouter()

# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {
            "telemetry": [],
            "alerts": [],
            "threats": [],
        }

    async def connect(self, ws: WebSocket, channel: str):
        await ws.accept()
        self.active.setdefault(channel, []).append(ws)
        logger.info(f"[WS] client connected to /{channel}, total={len(self.active[channel])}")

    def disconnect(self, ws: WebSocket, channel: str):
        if channel in self.active:
            self.active[channel] = [c for c in self.active[channel] if c != ws]

    async def broadcast(self, channel: str, data: Dict):
        if channel not in self.active:
            return
        dead = []
        for ws in self.active[channel]:
            try:
                await ws.send_text(json.dumps(data, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)


ws_manager = ConnectionManager()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mock_asset_list() -> List[Dict]:
    """Mock asset data for dev mode before DB is connected."""
    types = ["transformer", "circuit_breaker", "bess", "solar_farm", "wind_farm",
             "rtu", "substation", "capacitor_bank"]
    assets = []
    for i in range(1, 21):
        atype = types[i % len(types)]
        health = round(random.gauss(82, 12), 1)
        health = max(20.0, min(100.0, health))
        assets.append({
            "id": f"asset-{i:03d}",
            "name": f"{atype.replace('_', ' ').title()} {i:02d}",
            "asset_tag": f"{atype[:3].upper()}-{i:03d}",
            "asset_type": atype,
            "zone_id": f"zone-{(i % 3) + 1:02d}",
            "status": "online" if health > 40 else "degraded",
            "health_score": health,
            "rated_capacity_mw": round(random.uniform(50, 500), 0),
            "rated_voltage_kv": random.choice([34.5, 69.0, 115.0, 138.0, 230.0]),
            "latitude": 37.77 + random.uniform(-0.5, 0.5),
            "longitude": -122.41 + random.uniform(-0.5, 0.5),
            "last_seen": _now().isoformat(),
            "created_at": (_now() - timedelta(days=random.randint(30, 3650))).isoformat(),
            "updated_at": _now().isoformat(),
            "is_critical": i <= 5,
        })
    return assets


_ASSETS = _mock_asset_list()
_ALERTS = []
_THREATS = []


# ── Grid KPIs ────────────────────────────────────────────────────────────────

@router.get("/grid/kpis", response_model=GridKPIs, tags=["Grid"])
async def get_grid_kpis():
    """System-level KPIs: load, generation, frequency, renewable %, CO₂."""
    hour = _now().hour
    base_load = 4200 + random.gauss(0, 80)
    renewable_pct = 67.0 + random.gauss(0, 2)
    return GridKPIs(
        timestamp=_now(),
        total_load_mw=round(base_load, 1),
        total_generation_mw=round(base_load * 1.02, 1),
        renewable_mw=round(base_load * renewable_pct / 100, 1),
        renewable_pct=round(renewable_pct, 1),
        frequency_hz=round(random.gauss(60.0, 0.02), 4),
        transmission_capacity_used_pct=round(random.gauss(73, 2), 1),
        voltage_stability_index=round(random.gauss(0.94, 0.01), 3),
        co2_intensity_g_kwh=round(random.gauss(118, 5), 1),
        co2_avoided_tonnes_today=round(random.gauss(1840, 40), 0),
        system_inertia_pct=round(random.gauss(61, 3), 1),
        active_alerts=len([a for a in _ALERTS if a["status"] == "open"]) + 3,
        assets_online=len([a for a in _ASSETS if a["status"] == "online"]),
        assets_total=len(_ASSETS),
    )


@router.get("/grid/topology", tags=["Grid"])
async def get_grid_topology():
    """Live grid topology: nodes, connections, power flow."""
    return {
        "timestamp": _now().isoformat(),
        "nodes": [
            {"id": "solar-1", "type": "solar_farm", "name": "Solar Farm Alpha", "mw": 1200, "status": "online"},
            {"id": "wind-1",  "type": "wind_farm",  "name": "Wind Farm Beta",  "mw": 1640, "status": "online"},
            {"id": "peaker-1","type": "gas_peaker",  "name": "Peaker Unit 1",  "mw": 378,  "status": "online"},
            {"id": "sub-7a",  "type": "substation",  "name": "Substation 7A",  "voltage_kv": 138, "status": "online"},
            {"id": "bess-1",  "type": "bess",        "name": "BESS-1",         "mw": 460, "soc_pct": 78, "status": "online"},
            {"id": "load-ind","type": "load",         "name": "Industrial",    "mw": 2100, "status": "online"},
            {"id": "load-res","type": "load",         "name": "Residential",   "mw": 1180, "status": "online"},
        ],
        "edges": [
            {"from": "solar-1",  "to": "sub-7a",  "mw": 1200, "direction": "in"},
            {"from": "wind-1",   "to": "sub-7a",  "mw": 1640, "direction": "in"},
            {"from": "peaker-1", "to": "sub-7a",  "mw": 378,  "direction": "in"},
            {"from": "sub-7a",   "to": "load-ind","mw": 2100, "direction": "out"},
            {"from": "sub-7a",   "to": "load-res","mw": 1180, "direction": "out"},
            {"from": "sub-7a",   "to": "bess-1",  "mw": 180,  "direction": "charging"},
        ],
    }


@router.get("/grid/energy-mix", tags=["Grid"])
async def get_energy_mix():
    return {
        "timestamp": _now().isoformat(),
        "solar_mw": round(random.gauss(1200, 40), 0),
        "wind_mw": round(random.gauss(1640, 60), 0),
        "hydro_mw": round(random.gauss(460, 20), 0),
        "gas_mw": round(random.gauss(378, 15), 0),
        "import_mw": round(random.gauss(540, 25), 0),
        "bess_charging_mw": 180,
        "bess_discharging_mw": 0,
        "renewable_pct": round(random.gauss(67, 2), 1),
    }


# ── Assets ────────────────────────────────────────────────────────────────────

@router.get("/assets", tags=["Assets"])
async def list_assets(
    asset_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all monitored assets with optional filtering."""
    assets = _ASSETS
    if asset_type:
        assets = [a for a in assets if a["asset_type"] == asset_type]
    if status:
        assets = [a for a in assets if a["status"] == status]
    if zone_id:
        assets = [a for a in assets if a.get("zone_id") == zone_id]

    total = len(assets)
    start = (page - 1) * page_size
    return {
        "items": assets[start: start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/assets/{asset_id}", tags=["Assets"])
async def get_asset(asset_id: str):
    asset = next((a for a in _ASSETS if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return asset


@router.get("/assets/{asset_id}/health", tags=["Assets"])
async def get_asset_health(asset_id: str):
    asset = next((a for a in _ASSETS if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    health = asset["health_score"]
    fail_prob = health_scorer.predict_failure_probability(health)
    return {
        "asset_id": asset_id,
        "asset_name": asset["name"],
        "health_score": health,
        "status": asset["status"],
        "last_seen": asset["last_seen"],
        "failure_probability_30d": fail_prob,
        "next_maintenance": (_now() + timedelta(days=int(30 + (health / 100) * 90))).isoformat(),
        "active_alerts": random.randint(0, 3),
        "recent_anomalies": random.randint(0, 5),
        "telemetry_summary": {
            "active_power_mw": round(random.gauss(85, 5), 2),
            "voltage_kv": round(random.gauss(138, 0.5), 3),
            "frequency_hz": round(random.gauss(60.0, 0.02), 4),
            "temperature_c": round(random.gauss(68, 4), 1),
        },
    }


@router.get("/assets/{asset_id}/telemetry", tags=["Telemetry"])
async def get_asset_telemetry(
    asset_id: str,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
):
    """Recent telemetry readings for a specific asset."""
    asset = next((a for a in _ASSETS if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    readings = []
    for i in range(min(limit, hours * 2)):
        ts = _now() - timedelta(minutes=i * 30)
        readings.append({
            "timestamp": ts.isoformat(),
            "active_power_mw": round(random.gauss(85, 5), 3),
            "voltage_kv": round(random.gauss(138, 0.5), 3),
            "frequency_hz": round(random.gauss(60.0, 0.02), 4),
            "temperature_c": round(random.gauss(68, 3), 1),
        })
    return {"asset_id": asset_id, "readings": readings, "count": len(readings)}


# ── Forecasts ─────────────────────────────────────────────────────────────────

@router.get("/forecast/demand", tags=["Forecasting"])
async def get_demand_forecast(horizon_hours: int = Query(48, ge=1, le=168)):
    """AI-generated demand forecast up to 7 days ahead."""
    points = demand_forecaster.forecast(horizon_hours=horizon_hours)
    return {
        "forecast_type": "demand",
        "generated_at": _now().isoformat(),
        "model_version": demand_forecaster._model_version,
        "horizon_hours": horizon_hours,
        "points": points,
        "summary": {
            "peak_mw": max(p["value_mw"] for p in points),
            "min_mw": min(p["value_mw"] for p in points),
            "avg_mw": round(sum(p["value_mw"] for p in points) / len(points), 1),
        },
    }


@router.get("/forecast/renewable", tags=["Forecasting"])
async def get_renewable_forecast(horizon_hours: int = Query(12, ge=1, le=48)):
    """Combined solar + wind forecast with risk status."""
    points = renewable_forecaster.combined_forecast(
        solar_capacity_mw=1500,
        wind_capacity_mw=2200,
        horizon_hours=horizon_hours,
    )
    return {
        "forecast_type": "renewable",
        "generated_at": _now().isoformat(),
        "horizon_hours": horizon_hours,
        "points": points,
    }


@router.get("/forecast/recommendations", tags=["Forecasting"])
async def get_ai_recommendations():
    """AI dispatch and optimization recommendations."""
    kpis = {"renewable_pct": 67, "total_load_mw": 4218, "total_generation_mw": 4302}
    forecast = renewable_forecaster.combined_forecast(1500, 2200, horizon_hours=8)
    recs = recommendation_engine.generate(kpis, forecast, [])
    return {"recommendations": recs, "generated_at": _now().isoformat()}


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts", tags=["Alerts"])
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Active alert feed."""
    # Default alerts if none exist yet
    alerts = _ALERTS if _ALERTS else _default_alerts()
    if status:
        alerts = [a for a in alerts if a["status"] == status]
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    if category:
        alerts = [a for a in alerts if a.get("category") == category]
    return {"alerts": alerts[:limit], "total": len(alerts)}


@router.post("/alerts", tags=["Alerts"], status_code=status.HTTP_201_CREATED)
async def create_alert(alert: AlertCreate):
    new_alert = {
        "id": f"alert-{len(_ALERTS) + 1:04d}",
        **alert.model_dump(),
        "status": "open",
        "source": alert.source,
        "created_at": _now().isoformat(),
    }
    _ALERTS.append(new_alert)
    await emit(EventType.ALERT_CREATED, new_alert)
    await ws_manager.broadcast("alerts", {"type": "alert.created", "data": new_alert})
    return new_alert


@router.post("/alerts/{alert_id}/acknowledge", tags=["Alerts"])
async def acknowledge_alert(alert_id: str, body: AlertAcknowledge):
    alert = next((a for a in _ALERTS if a["id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["status"] = "acknowledged"
    alert["acknowledged_at"] = _now().isoformat()
    alert["acknowledged_by"] = body.acknowledged_by
    await emit(EventType.ALERT_ACKNOWLEDGED, alert)
    return alert


@router.post("/alerts/{alert_id}/resolve", tags=["Alerts"])
async def resolve_alert(alert_id: str, resolved_by: str = "operator"):
    alert = next((a for a in _ALERTS if a["id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["status"] = "resolved"
    alert["resolved_at"] = _now().isoformat()
    alert["resolved_by"] = resolved_by
    await emit(EventType.ALERT_RESOLVED, alert)
    return alert


def _default_alerts() -> List[Dict]:
    return [
        {
            "id": "alert-0001",
            "asset_id": "asset-004",
            "severity": "critical",
            "status": "open",
            "title": "Capacitor Bank C-07 — oil temperature abnormal",
            "description": "Dissolved gas analysis shows elevated ethylene. Thermal fault suspected.",
            "source": "ai",
            "category": "maintenance",
            "confidence": 0.91,
            "anomaly_score": 87.3,
            "recommended_action": "Dispatch crew for immediate inspection",
            "created_at": (_now() - timedelta(minutes=38)).isoformat(),
        },
        {
            "id": "alert-0002",
            "asset_id": None,
            "severity": "high",
            "status": "open",
            "title": "Wind ramp predicted — Zone 3 output drop",
            "description": "AI model forecasts 710 MW wind loss between 18:15–19:00. DR standby advised.",
            "source": "ai",
            "category": "operational",
            "confidence": 0.87,
            "recommended_action": "Arm demand response program",
            "created_at": (_now() - timedelta(minutes=62)).isoformat(),
        },
        {
            "id": "alert-0003",
            "asset_id": "asset-002",
            "severity": "medium",
            "status": "open",
            "title": "Circuit Breaker CB-12 — contact wear at 61%",
            "description": "Predictive model: 16% failure probability in 30 days.",
            "source": "ai",
            "category": "maintenance",
            "confidence": 0.79,
            "recommended_action": "Schedule replacement in next outage window",
            "created_at": (_now() - timedelta(hours=5)).isoformat(),
        },
    ]


# ── Maintenance ───────────────────────────────────────────────────────────────

@router.get("/maintenance", tags=["Maintenance"])
async def list_maintenance(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
):
    records = [
        {
            "id": "maint-001",
            "asset_id": "asset-004",
            "asset_name": "Capacitor Bank C-07",
            "maintenance_type": "predictive",
            "priority": "urgent",
            "title": "Oil sample analysis — thermal fault suspected",
            "failure_probability": 0.32,
            "predicted_failure_date": (_now() + timedelta(days=7)).isoformat(),
            "scheduled_date": None,
            "status": "open",
            "created_at": _now().isoformat(),
        },
        {
            "id": "maint-002",
            "asset_id": "asset-002",
            "asset_name": "Circuit Breaker CB-12",
            "maintenance_type": "predictive",
            "priority": "high",
            "title": "Contact wear replacement",
            "failure_probability": 0.16,
            "predicted_failure_date": (_now() + timedelta(days=30)).isoformat(),
            "scheduled_date": (_now() + timedelta(days=28)).isoformat(),
            "status": "scheduled",
            "created_at": _now().isoformat(),
        },
        {
            "id": "maint-003",
            "asset_id": "asset-001",
            "asset_name": "Transformer T-01A",
            "maintenance_type": "scheduled",
            "priority": "normal",
            "title": "Annual thermal scan",
            "failure_probability": 0.04,
            "predicted_failure_date": None,
            "scheduled_date": (_now() + timedelta(days=60)).isoformat(),
            "status": "scheduled",
            "created_at": _now().isoformat(),
        },
    ]
    if status:
        records = [r for r in records if r["status"] == status]
    if priority:
        records = [r for r in records if r["priority"] == priority]
    return {"records": records, "total": len(records)}


# ── Cybersecurity ─────────────────────────────────────────────────────────────

@router.get("/security/posture", tags=["Security"])
async def get_security_posture():
    return threat_engine.get_security_posture()


@router.get("/security/threats", tags=["Security"])
async def list_threats(active_only: bool = Query(True)):
    threats = [
        {
            "id": "threat-0001",
            "threat_level": "critical",
            "network_zone": "ot",
            "title": "Unauthorized SCADA protocol injection",
            "description": "Malformed Modbus/TCP frame on RTU-7A. CVE-2024-3811. Lateral movement blocked.",
            "source_ip": "10.44.8.231",
            "destination_ip": "10.55.1.12",
            "protocol": "modbus_tcp",
            "cve_id": "CVE-2024-3811",
            "attack_type": "Protocol injection",
            "threat_score": 92.0,
            "is_blocked": True,
            "is_active": True,
            "incident_ticket": "INC-2026-0847",
            "detected_at": (_now() - timedelta(minutes=38)).isoformat(),
        },
        {
            "id": "threat-0002",
            "threat_level": "high",
            "network_zone": "ot",
            "title": "Anomalous DNP3 polling frequency",
            "description": "Relay polling 8× above baseline. Possible reconnaissance.",
            "source_ip": "10.55.3.12",
            "protocol": "dnp3",
            "attack_type": "Reconnaissance",
            "threat_score": 68.0,
            "is_blocked": False,
            "is_active": True,
            "detected_at": (_now() - timedelta(hours=1)).isoformat(),
        },
    ]
    if active_only:
        threats = [t for t in threats if t["is_active"]]
    return {"threats": threats, "total": len(threats)}


@router.get("/security/zones", tags=["Security"])
async def get_zone_statuses():
    return {"zones": threat_engine.get_zone_statuses()}


@router.post("/security/evaluate-access", tags=["Security"])
async def evaluate_access(request: Dict):
    """Zero-trust policy evaluation for an access request."""
    result = zero_trust.evaluate(request)
    # Log to access log
    logger.info(f"[ZeroTrust] access {'allowed' if result['allowed'] else 'denied'} — {request}")
    return result


# ── Compliance ────────────────────────────────────────────────────────────────

@router.get("/compliance/nerc-cip", tags=["Compliance"])
async def get_nerc_cip_compliance():
    controls = compliance_checker.assess_all()
    overall = compliance_checker.overall_score(controls)
    return {
        "overall_score": overall,
        "controls": controls,
        "next_audit_days": 42,
        "nerc_region": "WECC",
        "generated_at": _now().isoformat(),
    }


@router.get("/compliance/summary", tags=["Compliance"])
async def get_compliance_summary():
    controls = compliance_checker.assess_all()
    overall = compliance_checker.overall_score(controls)
    critical_gaps = [c["control_id"] for c in controls if c["compliance_pct"] < 70]
    return ComplianceSummary(
        overall_score=overall,
        compliant_controls=len([c for c in controls if c["status"] == "compliant"]),
        total_controls=len(controls),
        critical_gaps=critical_gaps,
        next_audit_days=42,
        standards={"NERC_CIP": overall},
    )


# ── WebSocket endpoints ───────────────────────────────────────────────────────

@router.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    """Real-time telemetry stream — pushes asset readings every 5 seconds."""
    await ws_manager.connect(websocket, "telemetry")
    try:
        while True:
            # Push simulated live telemetry
            asset = random.choice(_ASSETS)
            event = {
                "type": "telemetry",
                "asset_id": asset["id"],
                "asset_name": asset["name"],
                "asset_type": asset["asset_type"],
                "timestamp": _now().isoformat(),
                "readings": {
                    "active_power_mw": round(random.gauss(85, 5), 3),
                    "voltage_kv": round(random.gauss(138, 0.5), 3),
                    "frequency_hz": round(random.gauss(60.0, 0.02), 4),
                    "temperature_c": round(random.gauss(68, 3), 1),
                },
            }
            await websocket.send_text(json.dumps(event, default=str))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "telemetry")


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """Real-time alert stream."""
    await ws_manager.connect(websocket, "alerts")
    # Send current open alerts immediately on connect
    current = _default_alerts()
    await websocket.send_text(json.dumps({
        "type": "alert.snapshot",
        "data": current,
    }, default=str))
    try:
        while True:
            # Listen for new alerts via event bus
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}, default=str))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "alerts")


@router.websocket("/ws/threats")
async def ws_threats(websocket: WebSocket):
    """Real-time security threat stream."""
    await ws_manager.connect(websocket, "threats")
    try:
        while True:
            await asyncio.sleep(60)
            await websocket.send_text(json.dumps({"type": "ping"}, default=str))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "threats")


# ── Health check ─────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": _now().isoformat(),
        "services": {
            "api": "online",
            "event_bus": "online",
            "ml_engine": "online",
            "telemetry_simulator": "online",
        },
    }
