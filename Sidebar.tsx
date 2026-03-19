"""
GridIQ Vegetation Engine — API Routes
======================================
REST endpoints for vegetation risk, LiDAR surveys, work orders,
NERC FAC-003 compliance, and fire weather overlays.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from backend.vegetation.lidar_ingest import lidar_manager
from backend.vegetation.risk_engine import (
    VegetationRiskScore, batch_scorer, risk_engine,
)
from backend.vegetation.transmission_lines import (
    get_all_spans, get_spans_by_line, get_spans_by_zone,
)
from backend.core.event_bus import EventType, emit

logger = logging.getLogger(__name__)
veg_router = APIRouter(prefix="/vegetation", tags=["Vegetation"])

# ── In-memory cache (replace with Redis/DB in production) ────────────────────
_scores_cache: Dict[str, VegetationRiskScore] = {}
_last_scored: Optional[datetime] = None
_scoring_in_progress = False


async def _ensure_scores_loaded(force: bool = False) -> None:
    """Score all spans if cache is empty or stale (>1 hour)."""
    global _scores_cache, _last_scored, _scoring_in_progress

    if _scoring_in_progress:
        return
    stale = (_last_scored is None or
             (datetime.now(timezone.utc) - _last_scored).seconds > 3600)
    if not force and not stale and _scores_cache:
        return

    _scoring_in_progress = True
    try:
        spans = get_all_spans()
        logger.info(f"[VegAPI] Scoring {len(spans)} spans...")
        scores = await batch_scorer.score_all_spans(spans, include_history=True)
        _scores_cache = {s.span_id: s for s in scores}
        _last_scored = datetime.now(timezone.utc)
        logger.info(f"[VegAPI] Scored {len(scores)} spans")

        # Emit critical alerts to the main event bus
        for score in scores:
            if score.risk_level in ("critical", "high"):
                await emit(EventType.ALERT_CREATED, {
                    "asset_id": None,
                    "severity": score.risk_level,
                    "status": "open",
                    "title": f"Vegetation risk — {score.line_name} span {score.span_id}",
                    "description": score.recommended_action,
                    "source": "vegetation_engine",
                    "category": "maintenance",
                    "confidence": score.overall_risk_score / 100,
                    "recommended_action": score.recommended_action,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
    finally:
        _scoring_in_progress = False


# ── Summary / dashboard KPIs ──────────────────────────────────────────────────

@veg_router.get("/summary")
async def get_vegetation_summary(background_tasks: BackgroundTasks):
    """
    Portfolio-level vegetation risk summary for dashboard KPI cards.
    Returns counts by risk level, NERC violation count, work order breakdown.
    """
    background_tasks.add_task(_ensure_scores_loaded)
    await _ensure_scores_loaded()

    scores = list(_scores_cache.values())
    stats = batch_scorer.summary_stats(scores)

    return {
        **stats,
        "last_scored": _last_scored.isoformat() if _last_scored else None,
        "nerc_standard": "FAC-003",
        "data_source": "USGS 3DEP + simulation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── All spans risk list ───────────────────────────────────────────────────────

@veg_router.get("/spans")
async def list_span_risks(
    risk_level: Optional[str] = Query(None, description="Filter: critical|high|medium|low"),
    line_id:    Optional[str] = Query(None, description="Filter by line ID"),
    zone:       Optional[str] = Query(None, description="Filter by zone"),
    priority:   Optional[str] = Query(None, description="Filter: immediate|30_days|90_days|annual"),
    limit:      int           = Query(50, ge=1, le=200),
    sort_by:    str           = Query("risk_score", description="risk_score|line|zone|violations"),
):
    """
    All span risk scores, sorted by risk descending by default.
    This is the main data source for the map view.
    """
    await _ensure_scores_loaded()
    scores = list(_scores_cache.values())

    if risk_level:
        scores = [s for s in scores if s.risk_level == risk_level]
    if line_id:
        spans_on_line = {sp.span_id for sp in get_spans_by_line(line_id)}
        scores = [s for s in scores if s.span_id in spans_on_line]
    if zone:
        spans_in_zone = {sp.span_id for sp in get_spans_by_zone(zone)}
        scores = [s for s in scores if s.span_id in spans_in_zone]
    if priority:
        scores = [s for s in scores if s.work_order_priority == priority]

    # Sort
    if sort_by == "violations":
        scores.sort(key=lambda s: s.clearance_violations, reverse=True)
    elif sort_by == "line":
        scores.sort(key=lambda s: s.line_name)
    elif sort_by == "zone":
        scores.sort(key=lambda s: s.span_id)
    else:
        scores.sort(key=lambda s: s.overall_risk_score, reverse=True)

    return {
        "spans": [_score_to_dict(s) for s in scores[:limit]],
        "total": len(scores),
        "filtered": len(scores),
    }


# ── Single span detail ────────────────────────────────────────────────────────

@veg_router.get("/spans/{span_id}")
async def get_span_detail(span_id: str):
    """Full risk detail for a single span including top 10 threat trees."""
    await _ensure_scores_loaded()
    score = _scores_cache.get(span_id)
    if not score:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")
    return _score_to_dict(score, include_threats=True)


# ── Raw LiDAR survey for a span ───────────────────────────────────────────────

@veg_router.get("/spans/{span_id}/survey")
async def get_span_survey(span_id: str):
    """
    Raw LiDAR point cloud data for a span.
    Returns canopy point positions and heights for 3D visualization.
    """
    spans = {s.span_id: s for s in get_all_spans()}
    span = spans.get(span_id)
    if not span:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")

    survey = await lidar_manager.get_survey(span)
    return {
        "span_id": span_id,
        "survey_date": survey.survey_date,
        "source": survey.source,
        "resolution_m": survey.resolution_m,
        "total_returns": survey.total_returns,
        "canopy_points": [
            {
                "lat": p.lat, "lon": p.lon,
                "height_m": p.height_m,
                "distance_to_conductor_m": p.distance_to_conductor_m,
                "classification": p.classification,
                "species": p.species_guess,
            }
            for p in survey.canopy_points[:500]  # limit for API response size
        ],
        "ground_points": survey.ground_points,
        "wire_points": survey.wire_points,
    }


# ── Historical trend for a span ───────────────────────────────────────────────

@veg_router.get("/spans/{span_id}/history")
async def get_span_history(span_id: str):
    """
    Year-over-year canopy height trend for a span.
    Shows vegetation growth trajectory toward NERC minimum clearance.
    """
    spans = {s.span_id: s for s in get_all_spans()}
    span = spans.get(span_id)
    if not span:
        raise HTTPException(status_code=404, detail=f"Span {span_id} not found")

    surveys = await lidar_manager.get_historical_surveys(span, years=3)

    history = []
    for s in surveys:
        if not s.canopy_points:
            continue
        heights = sorted([p.height_m for p in s.canopy_points])
        n = len(heights)
        history.append({
            "survey_date": s.survey_date,
            "source": s.source,
            "median_height_m": round(heights[n // 2], 2),
            "p90_height_m": round(heights[int(n * 0.9)], 2),
            "max_height_m": round(heights[-1], 2),
            "n_trees": n,
            "min_clearance_m": round(min(p.distance_to_conductor_m for p in s.canopy_points), 2),
        })

    return {
        "span_id": span_id,
        "nerc_min_clearance_m": risk_engine._engine._compute_growth_trend(surveys)[0]
        if hasattr(risk_engine, '_engine') else 3.05,
        "history": history,
    }


# ── Work order management ─────────────────────────────────────────────────────

@veg_router.get("/work-orders")
async def get_work_orders(
    priority: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    """
    Prioritized vegetation trim work orders generated from risk scores.
    These feed directly into the GridIQ maintenance module.
    """
    await _ensure_scores_loaded()

    priority_order = {"immediate": 0, "30_days": 1, "90_days": 2, "annual": 3}
    scores = sorted(
        _scores_cache.values(),
        key=lambda s: (priority_order.get(s.work_order_priority, 4), -s.overall_risk_score)
    )

    if priority:
        scores = [s for s in scores if s.work_order_priority == priority]

    work_orders = []
    for i, s in enumerate(scores[:limit]):
        spans = {sp.span_id: sp for sp in get_all_spans()}
        span = spans.get(s.span_id)
        work_orders.append({
            "work_order_id": f"WO-VEG-{i+1:04d}",
            "span_id": s.span_id,
            "line_name": s.line_name,
            "priority": s.work_order_priority,
            "risk_score": s.overall_risk_score,
            "risk_level": s.risk_level,
            "nerc_violations": s.clearance_violations,
            "encroaching_trees": s.encroaching_trees,
            "recommended_action": s.recommended_action,
            "dominant_species": s.dominant_species,
            "fire_risk_score": s.fire_risk_score,
            "lat": span.start.lat if span else None,
            "lon": span.start.lon if span else None,
            "estimated_crew_days": max(0.5, s.encroaching_trees * 0.2 + s.clearance_violations * 0.5),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    immediate = sum(1 for w in work_orders if w["priority"] == "immediate")
    return {
        "work_orders": work_orders,
        "total": len(work_orders),
        "immediate_count": immediate,
        "estimated_total_crew_days": round(sum(w["estimated_crew_days"] for w in work_orders), 1),
    }


@veg_router.post("/spans/{span_id}/record-trim")
async def record_trim_completion(span_id: str):
    """Mark a span as trimmed — resets risk score and work order."""
    risk_engine.record_trim(span_id)
    # Invalidate cache entry
    _scores_cache.pop(span_id, None)
    return {"status": "trim recorded", "span_id": span_id,
            "trim_date": datetime.now(timezone.utc).isoformat()}


# ── NERC FAC-003 compliance report ───────────────────────────────────────────

@veg_router.get("/compliance/fac-003")
async def get_fac003_compliance():
    """
    NERC FAC-003 vegetation management compliance report.
    Lists all clearance violations and risk of imminent violations.
    """
    await _ensure_scores_loaded()
    scores = list(_scores_cache.values())

    violations_detail = [
        {
            "span_id": s.span_id,
            "line_name": s.line_name,
            "voltage_kv": s.voltage_kv,
            "nerc_min_clearance_m": s.nerc_min_clearance_m,
            "min_observed_clearance_m": s.min_clearance_observed_m,
            "violation_count": s.clearance_violations,
            "risk_score": s.overall_risk_score,
        }
        for s in scores if s.clearance_violations > 0
    ]

    imminent = [
        {
            "span_id": s.span_id,
            "line_name": s.line_name,
            "years_to_violation": s.years_to_next_violation,
            "growth_rate_m_yr": s.growth_rate_m_yr,
            "dominant_species": s.dominant_species,
        }
        for s in scores
        if s.years_to_next_violation is not None and s.years_to_next_violation < 2
        and s.clearance_violations == 0
    ]
    imminent.sort(key=lambda x: x["years_to_violation"])

    total_violations = sum(s.clearance_violations for s in scores)
    compliance_pct = max(0, 100 - (total_violations / max(1, len(scores))) * 100)

    return {
        "standard": "NERC FAC-003-4",
        "compliance_pct": round(compliance_pct, 1),
        "status": "compliant" if total_violations == 0 else "non_compliant",
        "total_spans_assessed": len(scores),
        "spans_with_violations": len(violations_detail),
        "total_clearance_violations": total_violations,
        "violations": violations_detail,
        "imminent_violations": imminent[:10],
        "report_date": datetime.now(timezone.utc).isoformat(),
        "nerc_region": "WECC",
    }


# ── Fire risk overlay ─────────────────────────────────────────────────────────

@veg_router.get("/fire-risk")
async def get_fire_risk_overview():
    """
    Fire risk overlay combining vegetation data and current fire weather.
    Identifies spans where vegetation + Red Flag conditions create extreme risk.
    """
    await _ensure_scores_loaded()
    scores = list(_scores_cache.values())

    high_fire = sorted(
        [s for s in scores if s.fire_risk_score > 60],
        key=lambda s: s.fire_risk_score,
        reverse=True,
    )

    return {
        "red_flag_active": any(s.fire_risk_score > 85 for s in scores),
        "spans_at_extreme_fire_risk": sum(1 for s in scores if s.fire_risk_score > 85),
        "spans_at_high_fire_risk": sum(1 for s in scores if s.fire_risk_score > 60),
        "top_fire_risk_spans": [
            {
                "span_id": s.span_id,
                "line_name": s.line_name,
                "fire_risk_score": s.fire_risk_score,
                "dominant_species": s.dominant_species,
                "overall_risk_score": s.overall_risk_score,
            }
            for s in high_fire[:10]
        ],
        "data_source": "NOAA RAWS + vegetation model",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Line-level summary ────────────────────────────────────────────────────────

@veg_router.get("/lines")
async def get_lines_summary():
    """Summary risk scores aggregated by transmission line."""
    await _ensure_scores_loaded()
    scores = list(_scores_cache.values())
    spans_lookup = {s.span_id: s for s in get_all_spans()}

    lines: Dict[str, Dict] = {}
    for score in scores:
        span = spans_lookup.get(score.span_id)
        line_id = span.line_id if span else "unknown"
        if line_id not in lines:
            lines[line_id] = {
                "line_id": line_id,
                "line_name": score.line_name,
                "voltage_kv": score.voltage_kv,
                "span_count": 0,
                "avg_risk": 0.0,
                "max_risk": 0.0,
                "violations": 0,
                "critical_spans": 0,
                "scores": [],
            }
        d = lines[line_id]
        d["span_count"] += 1
        d["scores"].append(score.overall_risk_score)
        d["max_risk"] = max(d["max_risk"], score.overall_risk_score)
        d["violations"] += score.clearance_violations
        if score.risk_level == "critical":
            d["critical_spans"] += 1

    result = []
    for d in lines.values():
        s = d.pop("scores")
        d["avg_risk"] = round(sum(s) / len(s), 1) if s else 0.0
        d["risk_level"] = (
            "critical" if d["max_risk"] >= 80 else
            "high"     if d["max_risk"] >= 60 else
            "medium"   if d["max_risk"] >= 35 else "low"
        )
        result.append(d)

    result.sort(key=lambda d: d["max_risk"], reverse=True)
    return {"lines": result, "total": len(result)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_to_dict(score: VegetationRiskScore, include_threats: bool = False) -> Dict:
    spans = {s.span_id: s for s in get_all_spans()}
    span = spans.get(score.span_id)

    d = {
        "span_id":                  score.span_id,
        "line_name":                score.line_name,
        "voltage_kv":               score.voltage_kv,
        "overall_risk_score":       score.overall_risk_score,
        "risk_level":               score.risk_level,
        "nerc_min_clearance_m":     score.nerc_min_clearance_m,
        "min_clearance_observed_m": score.min_clearance_observed_m,
        "clearance_violations":     score.clearance_violations,
        "encroaching_trees":        score.encroaching_trees,
        "total_trees_in_corridor":  score.total_trees_in_corridor,
        "canopy_cover_pct":         score.canopy_cover_pct,
        "growth_rate_m_yr":         score.growth_rate_m_yr,
        "years_to_next_violation":  score.years_to_next_violation,
        "dominant_species":         score.dominant_species,
        "fire_risk_score":          score.fire_risk_score,
        "terrain_risk_multiplier":  score.terrain_risk_multiplier,
        "last_trim_days_ago":       score.last_trim_days_ago,
        "recommended_action":       score.recommended_action,
        "work_order_priority":      score.work_order_priority,
        "trend":                    score.trend,
        "growth_trend_m_yr":        score.growth_trend_m_yr,
        "survey_date":              score.survey_date,
        # Map position (midpoint of span)
        "lat": ((span.start.lat + span.end.lat) / 2) if span else None,
        "lon": ((span.start.lon + span.end.lon) / 2) if span else None,
        "span_length_m": span.length_m if span else None,
        "zone": span.zone if span else None,
    }
    if include_threats:
        d["top_threats"] = [
            {
                "lat": t.lat, "lon": t.lon,
                "height_m": t.height_m,
                "species": t.species,
                "distance_to_conductor_m": t.distance_to_conductor_m,
                "clearance_deficit_m": t.clearance_deficit_m,
                "growth_rate_m_yr": t.growth_rate_m_yr,
                "years_to_violation": t.years_to_violation,
                "threat_score": t.threat_score,
            }
            for t in score.threats
        ]
    return d
