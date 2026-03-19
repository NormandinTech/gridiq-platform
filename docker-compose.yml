"""
GridIQ Sensor Management — API Routes
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from backend.sensors.catalog import (
    SENSOR_CATALOG, SensorCategory, get_sensors_for_asset_type,
    get_sensors_by_category, get_critical_sensors, total_sensor_cost,
)
from backend.sensors.registry import (
    DeployedSensor, DeploymentStatus, sensor_registry,
)

logger = logging.getLogger(__name__)
sensor_router = APIRouter(prefix="/sensors", tags=["Sensors"])


# ── Fleet summary ─────────────────────────────────────────────────────────────

@sensor_router.get("/summary")
async def get_sensor_summary():
    s = sensor_registry.summary()
    return {**s, "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Deployed sensors ──────────────────────────────────────────────────────────

@sensor_router.get("/deployed")
async def list_deployed_sensors(
    asset_id:      Optional[str]   = Query(None),
    asset_type:    Optional[str]   = Query(None),
    status:        Optional[str]   = Query(None),
    quality_below: Optional[float] = Query(None),
    limit:         int             = Query(100, ge=1, le=500),
):
    sensors = sensor_registry.list_all(
        asset_id=asset_id, asset_type=asset_type,
        status=status, quality_below=quality_below,
    )
    sensors.sort(key=lambda s: s.data_quality_score)
    return {
        "sensors": [_sensor_to_dict(s) for s in sensors[:limit]],
        "total": len(sensors),
    }


@sensor_router.get("/deployed/{sensor_id}")
async def get_deployed_sensor(sensor_id: str):
    s = sensor_registry.get(sensor_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Sensor {sensor_id} not found")
    return _sensor_to_dict(s, include_spec=True)


@sensor_router.post("/deployed/{sensor_id}/calibrate")
async def record_calibration(sensor_id: str):
    s = sensor_registry.record_calibration(sensor_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Sensor {sensor_id} not found")
    return {
        "sensor_id": sensor_id,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "next_calibration_date": s.next_calibration_date,
        "new_quality_score": s.data_quality_score,
    }


@sensor_router.post("/deployed/{sensor_id}/status")
async def update_sensor_status(sensor_id: str, status: str):
    try:
        new_status = DeploymentStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    s = sensor_registry.update_status(sensor_id, new_status)
    if not s:
        raise HTTPException(status_code=404, detail=f"Sensor {sensor_id} not found")
    return {"sensor_id": sensor_id, "status": s.status.value, "quality_score": s.data_quality_score}


# ── Calibration schedule ──────────────────────────────────────────────────────

@sensor_router.get("/calibration-schedule")
async def get_calibration_schedule():
    schedule = sensor_registry.calibration_schedule()
    overdue = [s for s in schedule if s["overdue"]]
    due_30  = [s for s in schedule if not s["overdue"] and s["days_until_due"] <= 30]
    return {
        "overdue_count": len(overdue),
        "due_in_30_days": len(due_30),
        "schedule": schedule,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Data quality report ───────────────────────────────────────────────────────

@sensor_router.get("/data-quality")
async def get_data_quality_report():
    from backend.sensors.registry import DataQualityScorer
    scorer = DataQualityScorer()
    sensors = sensor_registry.list_all()
    report = []
    for s in sensors:
        spec = next((sp for sp in SENSOR_CATALOG if sp.sensor_type_id == s.sensor_type_id), None)
        report.append({
            "sensor_id":          s.sensor_id,
            "asset_name":         s.asset_name,
            "sensor_name":        spec.name if spec else s.sensor_type_id,
            "quality_score":      s.data_quality_score,
            "quality_label":      scorer.quality_label(s.data_quality_score),
            "availability_pct":   s.availability_pct_30d,
            "outlier_rate_pct":   s.outlier_rate_pct,
            "drift_detected":     s.drift_detected,
            "status":             s.status.value,
            "alerts":             s.alerts,
        })
    report.sort(key=lambda r: r["quality_score"])
    avg = sum(r["quality_score"] for r in report) / len(report) if report else 0
    return {
        "avg_quality_score":  round(avg, 1),
        "poor_count":         sum(1 for r in report if r["quality_score"] < 70),
        "sensors":            report,
        "generated_at":       datetime.now(timezone.utc).isoformat(),
    }


# ── Sensor catalog ────────────────────────────────────────────────────────────

@sensor_router.get("/catalog")
async def browse_catalog(
    asset_type: Optional[str] = Query(None),
    category:   Optional[str] = Query(None),
    priority:   Optional[str] = Query(None),
):
    specs = SENSOR_CATALOG
    if asset_type:
        specs = get_sensors_for_asset_type(asset_type)
    if category:
        try:
            cat = SensorCategory(category)
            specs = [s for s in specs if s.category == cat]
        except ValueError:
            pass
    if priority:
        specs = [s for s in specs if s.priority == priority]

    return {
        "sensors": [_spec_to_dict(s) for s in specs],
        "total": len(specs),
        "categories": [c.value for c in SensorCategory],
    }


@sensor_router.get("/catalog/{sensor_type_id}")
async def get_sensor_spec(sensor_type_id: str):
    spec = next((s for s in SENSOR_CATALOG if s.sensor_type_id == sensor_type_id), None)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Sensor type {sensor_type_id} not found")
    return _spec_to_dict(spec)


@sensor_router.get("/catalog/for-asset/{asset_type}")
async def get_sensors_for_asset(asset_type: str):
    specs = get_sensors_for_asset_type(asset_type)
    if not specs:
        raise HTTPException(status_code=404, detail=f"No sensors found for asset type: {asset_type}")
    total_lo = sum(s.cost_usd_lo or 0 for s in specs)
    total_hi = sum(s.cost_usd_hi or 0 for s in specs)
    return {
        "asset_type":     asset_type,
        "sensor_count":   len(specs),
        "sensors":        [_spec_to_dict(s) for s in specs],
        "total_cost_lo":  total_lo,
        "total_cost_hi":  total_hi,
        "critical_count": sum(1 for s in specs if s.priority == "critical"),
    }


@sensor_router.post("/catalog/estimate-cost")
async def estimate_sensor_cost(sensor_type_ids: List[str]):
    cost = total_sensor_cost(sensor_type_ids, include_install=True)
    return {
        "sensor_count": len(sensor_type_ids),
        "estimated_cost_lo": cost["low"],
        "estimated_cost_hi": cost["high"],
        "install_cost":      cost["install_only"],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sensor_to_dict(s: DeployedSensor, include_spec: bool = False) -> Dict:
    spec = next((sp for sp in SENSOR_CATALOG if sp.sensor_type_id == s.sensor_type_id), None)
    d = {
        "sensor_id":            s.sensor_id,
        "sensor_type_id":       s.sensor_type_id,
        "sensor_name":          spec.name if spec else s.sensor_type_id,
        "category":             spec.category.value if spec else None,
        "asset_id":             s.asset_id,
        "asset_name":           s.asset_name,
        "asset_type":           s.asset_type,
        "manufacturer":         s.manufacturer,
        "model":                s.model,
        "serial_number":        s.serial_number,
        "firmware_version":     s.firmware_version,
        "installation_point":   s.installation_point,
        "status":               s.status.value,
        "install_date":         s.install_date,
        "last_calibration_date":s.last_calibration_date,
        "next_calibration_date":s.next_calibration_date,
        "last_seen":            s.last_seen,
        "data_quality_score":   s.data_quality_score,
        "availability_pct_30d": s.availability_pct_30d,
        "outlier_rate_pct":     s.outlier_rate_pct,
        "drift_detected":       s.drift_detected,
        "protocol":             s.protocol,
        "ip_address":           s.ip_address,
        "purchase_cost_usd":    s.purchase_cost_usd,
        "alerts":               s.alerts,
        "notes":                s.notes,
        "feeds_fault_codes":    spec.feeds_fault_codes if spec else [],
    }
    if include_spec and spec:
        d["spec"] = _spec_to_dict(spec)
    return d


def _spec_to_dict(s: SensorSpec) -> Dict:
    return {
        "sensor_type_id":       s.sensor_type_id,
        "name":                 s.name,
        "category":             s.category.value,
        "description":          s.description,
        "compatible_asset_types": s.compatible_asset_types,
        "feeds_fault_codes":    s.feeds_fault_codes,
        "measurement_parameter":s.measurement_parameter,
        "measurement_unit":     s.measurement_unit,
        "measurement_range_lo": s.measurement_range_lo,
        "measurement_range_hi": s.measurement_range_hi,
        "accuracy_pct":         s.accuracy_pct,
        "sample_rate_hz":       s.sample_rate_hz,
        "protocols":            s.protocols,
        "ip_rating":            s.ip_rating,
        "calibration_frequency":s.calibration_frequency.value,
        "calibration_method":   s.calibration_method,
        "cost_usd_lo":          s.cost_usd_lo,
        "cost_usd_hi":          s.cost_usd_hi,
        "install_cost_usd":     s.install_cost_usd,
        "lead_time_weeks":      s.lead_time_weeks,
        "manufacturers":        s.manufacturers,
        "roi_description":      s.roi_description,
        "priority":             s.priority,
    }
