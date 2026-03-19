"""
GridIQ Asset Intelligence — API Routes
=======================================
REST endpoints for fleet-wide fault detection, energy losses,
outage tracking, and maintenance work orders across all asset types.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from backend.assets.fault_detector import (
    DetectedFault, FaultCategory, FaultSeverity,
    fault_detector, fleet_scanner,
)
from backend.assets.fault_signatures import (
    FAULT_SIGNATURES, ALL_ASSET_TYPES,
    get_signatures_for_asset_type,
)

logger = logging.getLogger(__name__)
asset_router = APIRouter(prefix="/asset-intelligence", tags=["Asset Intelligence"])

# ── Seed some demo faults on startup ─────────────────────────────────────────

def _seed_demo_faults():
    """Pre-populate realistic faults across the demo asset fleet."""
    import asyncio

    demo_assets = [
        # Hydro
        {"asset_id":"hydro-001","asset_name":"Shasta Dam Unit 3","asset_type":"hydro_plant",
         "active_power_mw":55.0,"vibration_rms_mms":9.2,"efficiency_pct":87.5,
         "water_flow_m3s":280,"net_head_m":95,"asset_meta":{"rated_capacity_mw":110}},
        {"asset_id":"dam-001","asset_name":"Folsom Dam","asset_type":"dam",
         "active_power_mw":0,"seepage_flow_ls":52.0,"reservoir_level_pct":58.0,
         "asset_meta":{"rated_capacity_mw":0}},
        # Solar
        {"asset_id":"solar-001","asset_name":"Solar Farm Alpha","asset_type":"solar_farm",
         "active_power_mw":180,"irradiance_wm2":820,"performance_ratio":0.72,
         "string_current_ratio":0.03,"asset_meta":{"rated_capacity_mw":300}},
        {"asset_id":"solar-002","asset_name":"Solar Farm Beta","asset_type":"solar_farm",
         "active_power_mw":0,"irradiance_wm2":750,"asset_meta":{"rated_capacity_mw":450}},
        # Wind
        {"asset_id":"wind-001","asset_name":"Wind Farm North T-12","asset_type":"wind_farm",
         "active_power_mw":1.2,"wind_speed_ms":14,"gearbox_vibration_g":5.8,
         "generator_temp_c":127,"asset_meta":{"rated_capacity_mw":3.6}},
        {"asset_id":"wind-002","asset_name":"Wind Farm East","asset_type":"wind_farm",
         "active_power_mw":320,"wind_speed_ms":11,"yaw_error_deg":11.5,
         "asset_meta":{"rated_capacity_mw":600}},
        # Gas
        {"asset_id":"gas-001","asset_name":"Peaker Unit 1","asset_type":"gas_peaker",
         "active_power_mw":190,"heat_rate_btu_kwh":10400,"exhaust_temp_spread_c":35.0,
         "nox_ppm":4.7,"fuel_flow_mscfd":12,"asset_meta":{"rated_capacity_mw":200}},
        # BESS
        {"asset_id":"bess-001","asset_name":"BESS-1 Tesla Megapack","asset_type":"bess",
         "active_power_mw":-80,"state_of_charge_pct":78,"cell_temp_max_c":28,
         "state_of_health_pct":91,"roundtrip_efficiency_pct":91.5,
         "asset_meta":{"rated_capacity_mw":460}},
        {"asset_id":"bess-002","asset_name":"BESS-2 South Substation","asset_type":"bess",
         "active_power_mw":0,"state_of_charge_pct":45,"cell_temp_max_c":52.0,
         "cell_voltage_spread_mv":65,"state_of_health_pct":76,
         "asset_meta":{"rated_capacity_mw":200}},
        # Transmission
        {"asset_id":"txn-001","asset_name":"Sierra 230kV Line","asset_type":"transmission_line",
         "active_power_mw":185,"conductor_temp_c":88,"partial_discharge_pC":620,
         "dynamic_line_rating_pct":102,"asset_meta":{"rated_capacity_mw":400}},
        # Smart meters (cluster)
        {"asset_id":"ami-001","asset_name":"Meter Cluster Zone-7","asset_type":"smart_meter",
         "active_power_mw":0.008,"hours_since_last_reading":28,"voltage_imbalance_pct":3.8,
         "consumption_anomaly_score":0.0,"asset_meta":{"rated_capacity_mw":0}},
    ]

    async def _seed():
        for a in demo_assets:
            meta = a.pop("asset_meta", {})
            fault_detector.detect(
                asset_id=a["asset_id"],
                asset_name=a["asset_name"],
                asset_type=a["asset_type"],
                telemetry=a,
                asset_meta=meta,
            )

    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_seed())
        else:
            loop.run_until_complete(_seed())
    except Exception:
        pass


# Seed on module load
_seed_demo_faults()


# ── Summary / fleet health ────────────────────────────────────────────────────

@asset_router.get("/summary")
async def get_fleet_summary():
    """
    Fleet-wide fault and loss summary — the top-level KPI cards
    for the Asset Intelligence dashboard.
    """
    s = fault_detector.summary
    faults = fault_detector.get_active_faults()

    outage_assets = [f.asset_name for f in faults if f.category == FaultCategory.OUTAGE]

    return {
        **s,
        "outage_assets": outage_assets,
        "top_fault": faults[0].title if faults else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Active faults ─────────────────────────────────────────────────────────────

@asset_router.get("/faults")
async def list_faults(
    severity:   Optional[str] = Query(None),
    category:   Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    asset_id:   Optional[str] = Query(None),
    limit:      int           = Query(50, ge=1, le=200),
):
    """
    All active detected faults across the entire fleet.
    Sorted by severity then detection time.
    """
    faults = fault_detector.get_active_faults(asset_id=asset_id)

    if severity:
        try:
            sev = FaultSeverity(severity)
            faults = [f for f in faults if f.severity == sev]
        except ValueError:
            pass

    if category:
        try:
            cat = FaultCategory(category)
            faults = [f for f in faults if f.category == cat]
        except ValueError:
            pass

    if asset_type:
        faults = [f for f in faults if f.asset_type == asset_type]

    return {
        "faults": [_fault_to_dict(f) for f in faults[:limit]],
        "total": len(faults),
        "by_severity": {
            sev.value: sum(1 for f in faults if f.severity == sev)
            for sev in FaultSeverity
        },
    }


@asset_router.get("/faults/{fault_id}")
async def get_fault(fault_id: str):
    """Detail for a single fault."""
    all_faults = fault_detector.get_active_faults()
    fault = next((f for f in all_faults if f.fault_id == fault_id), None)
    if not fault:
        raise HTTPException(status_code=404, detail=f"Fault {fault_id} not found")
    return _fault_to_dict(fault)


@asset_router.post("/faults/{asset_id}/{fault_code}/resolve")
async def resolve_fault(asset_id: str, fault_code: str):
    """Mark a fault as resolved after maintenance completion."""
    resolved = fault_detector.resolve_fault(asset_id, fault_code)
    return {
        "resolved": resolved,
        "asset_id": asset_id,
        "fault_code": fault_code,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Outage tracking ───────────────────────────────────────────────────────────

@asset_router.get("/outages")
async def get_outages():
    """All current outages — complete generation loss events."""
    outages = [
        f for f in fault_detector.get_active_faults()
        if f.category == FaultCategory.OUTAGE
    ]
    total_loss_mw = sum(f.estimated_loss_mw or 0 for f in outages)
    total_revenue = sum(f.estimated_revenue_loss_hr or 0 for f in outages)

    return {
        "outages": [_fault_to_dict(f) for f in outages],
        "count": len(outages),
        "total_loss_mw": round(total_loss_mw, 1),
        "total_revenue_loss_per_hour": round(total_revenue, 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Energy losses ─────────────────────────────────────────────────────────────

@asset_router.get("/energy-losses")
async def get_energy_losses():
    """All assets producing below theoretical output."""
    losses = [
        f for f in fault_detector.get_active_faults()
        if f.category == FaultCategory.EFFICIENCY_LOSS or f.fault_code == "GEN-LOSS"
    ]
    losses.sort(key=lambda f: f.estimated_loss_mw or 0, reverse=True)

    total_loss = sum(f.estimated_loss_mw or 0 for f in losses)
    total_rev  = sum(f.estimated_revenue_loss_hr or 0 for f in losses)

    return {
        "losses": [_fault_to_dict(f) for f in losses],
        "count": len(losses),
        "total_loss_mw": round(total_loss, 2),
        "total_revenue_loss_per_hour": round(total_rev, 0),
        "annual_revenue_impact": round(total_rev * 8760, 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Work orders ───────────────────────────────────────────────────────────────

@asset_router.get("/work-orders")
async def get_work_orders(
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Maintenance work orders generated from detected faults.
    Sorted by urgency — critical + outages first.
    """
    faults = fault_detector.get_active_faults()
    priority_order = {"immediate": 0, "same_day": 1, "7_days": 2, "scheduled": 3, "monitor": 4}

    if priority:
        faults = [f for f in faults if f.work_order_priority == priority]

    faults.sort(key=lambda f: (
        priority_order.get(f.work_order_priority, 5),
        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity.value, 4),
    ))

    work_orders = []
    for i, f in enumerate(faults[:limit]):
        work_orders.append({
            "work_order_id":      f"WO-AI-{i+1:04d}",
            "fault_id":           f.fault_id,
            "fault_code":         f.fault_code,
            "asset_id":           f.asset_id,
            "asset_name":         f.asset_name,
            "asset_type":         f.asset_type,
            "priority":           f.work_order_priority,
            "severity":           f.severity.value,
            "category":           f.category.value,
            "title":              f.title,
            "recommended_action": f.recommended_action,
            "maintenance_type":   f.maintenance_type,
            "estimated_loss_mw":  f.estimated_loss_mw,
            "revenue_loss_hr":    f.estimated_revenue_loss_hr,
            "detected_at":        f.detected_at,
            "confidence":         f.confidence,
        })

    immediate = sum(1 for w in work_orders if w["priority"] == "immediate")
    total_loss = sum(w["estimated_loss_mw"] or 0 for w in work_orders)

    return {
        "work_orders":      work_orders,
        "total":            len(work_orders),
        "immediate_count":  immediate,
        "total_loss_mw":    round(total_loss, 1),
    }


# ── Asset type breakdown ──────────────────────────────────────────────────────

@asset_router.get("/by-asset-type")
async def get_by_asset_type():
    """Fault counts and losses broken down by asset type."""
    faults = fault_detector.get_active_faults()
    by_type: Dict[str, Dict] = {}

    for f in faults:
        t = f.asset_type
        if t not in by_type:
            by_type[t] = {
                "asset_type": t,
                "fault_count": 0,
                "critical": 0,
                "high": 0,
                "outages": 0,
                "total_loss_mw": 0.0,
                "revenue_loss_hr": 0.0,
            }
        by_type[t]["fault_count"] += 1
        if f.severity == FaultSeverity.CRITICAL:
            by_type[t]["critical"] += 1
        if f.severity == FaultSeverity.HIGH:
            by_type[t]["high"] += 1
        if f.category == FaultCategory.OUTAGE:
            by_type[t]["outages"] += 1
        by_type[t]["total_loss_mw"] += f.estimated_loss_mw or 0
        by_type[t]["revenue_loss_hr"] += f.estimated_revenue_loss_hr or 0

    for v in by_type.values():
        v["total_loss_mw"]   = round(v["total_loss_mw"], 1)
        v["revenue_loss_hr"] = round(v["revenue_loss_hr"], 0)

    result = sorted(by_type.values(), key=lambda x: x["fault_count"], reverse=True)
    return {"by_type": result}


# ── Fault signature library ───────────────────────────────────────────────────

@asset_router.get("/signatures")
async def get_fault_signatures(asset_type: Optional[str] = Query(None)):
    """Browse the fault signature library — what the engine detects and how."""
    sigs = get_signatures_for_asset_type(asset_type) if asset_type else FAULT_SIGNATURES
    return {
        "signatures": [
            {
                "fault_code":        s.fault_code,
                "name":              s.name,
                "asset_types":       s.asset_types,
                "category":          s.category.value,
                "severity":          s.severity.value,
                "description":       s.description,
                "detection_method":  s.detection_method,
                "recommended_action":s.recommended_action,
                "nerc_standard":     s.nerc_standard,
                "maintenance_type":  s.maintenance_type,
            }
            for s in sigs
        ],
        "total": len(sigs),
        "asset_types_covered": ALL_ASSET_TYPES,
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _fault_to_dict(f: DetectedFault) -> Dict:
    return {
        "fault_id":                f.fault_id,
        "fault_code":              f.fault_code,
        "asset_id":                f.asset_id,
        "asset_name":              f.asset_name,
        "asset_type":              f.asset_type,
        "severity":                f.severity.value,
        "category":                f.category.value,
        "title":                   f.title,
        "description":             f.description,
        "detected_at":             f.detected_at,
        "trigger_param":           f.trigger_param,
        "trigger_value":           f.trigger_value,
        "trigger_threshold":       f.trigger_threshold,
        "estimated_loss_mw":       f.estimated_loss_mw,
        "estimated_revenue_loss_hr": f.estimated_revenue_loss_hr,
        "recommended_action":      f.recommended_action,
        "work_order_priority":     f.work_order_priority,
        "maintenance_type":        f.maintenance_type,
        "confidence":              f.confidence,
        "status":                  f.status,
    }
