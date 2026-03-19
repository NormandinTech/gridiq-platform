"""
GridIQ Vegetation Engine — Risk Scoring
========================================
Turns raw LiDAR point clouds into actionable risk scores per span.

Risk model combines:
  1. Clearance deficit         — how close is the tallest tree to the conductor
  2. Growth rate trend         — year-over-year canopy height increase
  3. Species risk factor       — fast-growing / fire-prone species score higher
  4. Fire weather overlay      — NOAA RAWS station data, Red Flag conditions
  5. Terrain multiplier        — steep slopes accelerate tree lean toward wires
  6. Encroachment density      — number of trees within minimum clearance zone
  7. Time since last trim       — work order history factor

NERC FAC-003 minimum clearances (simplified):
  - 115–230 kV:  3.05m minimum at max sag/temp
  - 345 kV:      4.27m minimum
  - 500 kV:      6.10m minimum
  - 765 kV:      7.62m minimum
"""
from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.vegetation.lidar_ingest import (
    CanopyPoint, SpanLiDARSurvey, TransmissionSpan, lidar_manager
)

logger = logging.getLogger(__name__)


# ── NERC FAC-003 clearance requirements ──────────────────────────────────────

NERC_MIN_CLEARANCE_M: Dict[str, float] = {
    "115kv":  3.05,
    "230kv":  3.05,
    "345kv":  4.27,
    "500kv":  6.10,
    "765kv":  7.62,
    "default": 3.05,
}

def nerc_clearance(voltage_kv: float) -> float:
    if voltage_kv <= 115:   return 3.05
    elif voltage_kv <= 230: return 3.05
    elif voltage_kv <= 345: return 4.27
    elif voltage_kv <= 500: return 6.10
    else:                   return 7.62


# ── Species risk table ────────────────────────────────────────────────────────
# (growth_rate_m_per_yr, fire_risk_0_1, failure_risk_0_1)

SPECIES_RISK: Dict[str, Dict[str, float]] = {
    "eucalyptus":     {"growth": 1.8, "fire": 0.95, "failure": 0.70},
    "ponderosa_pine": {"growth": 0.6, "fire": 0.80, "failure": 0.55},
    "live_oak":       {"growth": 0.4, "fire": 0.55, "failure": 0.40},
    "blue_gum":       {"growth": 2.0, "fire": 0.95, "failure": 0.75},
    "cottonwood":     {"growth": 1.2, "fire": 0.30, "failure": 0.65},
    "willow":         {"growth": 1.5, "fire": 0.25, "failure": 0.60},
    "chaparral":      {"growth": 0.5, "fire": 0.85, "failure": 0.30},
    "shrub":          {"growth": 0.3, "fire": 0.60, "failure": 0.20},
    "unknown":        {"growth": 0.7, "fire": 0.60, "failure": 0.45},
}


# ── Risk scoring output ───────────────────────────────────────────────────────

@dataclass
class TreeThreat:
    """A single encroaching tree with its risk contribution."""
    lat: float
    lon: float
    height_m: float
    species: str
    distance_to_conductor_m: float
    nerc_min_clearance_m: float
    clearance_deficit_m: float       # negative = violation
    growth_rate_m_yr: float
    years_to_violation: Optional[float]  # None = already in violation
    fire_risk: float
    failure_risk: float
    threat_score: float              # 0–100


@dataclass
class VegetationRiskScore:
    """Complete risk assessment for one transmission span."""
    span_id: str
    line_name: str
    voltage_kv: float
    survey_date: str
    overall_risk_score: float        # 0–100
    risk_level: str                  # critical | high | medium | low
    nerc_min_clearance_m: float
    min_clearance_observed_m: float  # closest any tree came to conductor
    clearance_violations: int        # trees below NERC minimum
    encroaching_trees: int           # trees within 2× NERC minimum
    total_trees_in_corridor: int
    canopy_cover_pct: float
    growth_rate_m_yr: float          # average annual growth in corridor
    years_to_next_violation: Optional[float]
    dominant_species: str
    fire_risk_score: float           # 0–100
    terrain_risk_multiplier: float   # 1.0 = flat, higher = steeper
    last_trim_days_ago: Optional[int]
    recommended_action: str
    work_order_priority: str         # immediate | 30_days | 90_days | annual
    threats: List[TreeThreat] = field(default_factory=list)
    trend: str = "stable"            # improving | stable | worsening
    growth_trend_m_yr: float = 0.0


# ── Fire weather integration ──────────────────────────────────────────────────

class FireWeatherService:
    """
    Fetches fire weather data from NOAA RAWS (Remote Automated Weather Stations).
    Red Flag conditions drastically increase risk scoring.

    Production API: https://www.wrcc.dri.edu/cgi-bin/wea_dysimts.pl
    NOAA RAWS: https://www.ncei.noaa.gov/access/monitoring/fire-weather/
    """

    def get_conditions(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Get current fire weather conditions for a location.
        Returns: {red_flag, rh_pct, wind_mph, temp_f, drought_index}
        """
        try:
            import httpx
            # In production: query nearest RAWS station
            # For now: return realistic simulated conditions
            pass
        except ImportError:
            pass

        # Simulated — varies by season/location
        month = datetime.now().month
        is_dry_season = month in (6, 7, 8, 9, 10)  # June–Oct fire season

        rh = random.gauss(25 if is_dry_season else 55, 10)
        wind = random.gauss(18 if is_dry_season else 8, 5)
        temp = random.gauss(95 if is_dry_season else 65, 8)
        drought = random.gauss(600 if is_dry_season else 200, 80)  # Keetch-Byram

        red_flag = (rh < 25 and wind > 25) or drought > 700

        return {
            "red_flag": red_flag,
            "rh_pct": round(max(5, rh), 1),
            "wind_mph": round(max(0, wind), 1),
            "temp_f": round(temp, 1),
            "drought_index_kbdi": round(max(0, drought), 0),
            "station_id": f"RAWS_{abs(int(lat*10))}{abs(int(lon*10))}",
        }

    def risk_multiplier(self, conditions: Dict) -> float:
        """Convert fire weather to a risk score multiplier (1.0–2.5)."""
        mult = 1.0
        if conditions["red_flag"]:
            mult += 1.0
        if conditions["rh_pct"] < 15:
            mult += 0.4
        elif conditions["rh_pct"] < 25:
            mult += 0.2
        if conditions["wind_mph"] > 30:
            mult += 0.3
        if conditions["drought_index_kbdi"] > 600:
            mult += 0.3
        return round(min(2.5, mult), 2)


# ── Core risk engine ──────────────────────────────────────────────────────────

class VegetationRiskEngine:
    """
    Main risk scoring engine.
    Input:  TransmissionSpan + SpanLiDARSurvey(s)
    Output: VegetationRiskScore
    """

    def __init__(self):
        self._fire_weather = FireWeatherService()
        self._trim_history: Dict[str, datetime] = {}  # span_id -> last trim date

    def score_span(
        self,
        span: TransmissionSpan,
        current_survey: SpanLiDARSurvey,
        historical_surveys: Optional[List[SpanLiDARSurvey]] = None,
    ) -> VegetationRiskScore:
        """
        Full risk assessment for one span.
        """
        nerc_min = nerc_clearance(span.voltage_kv)
        canopy = current_survey.canopy_points
        mid_lat = (span.start.lat + span.end.lat) / 2
        mid_lon = (span.start.lon + span.end.lon) / 2

        # ── 1. Clearance analysis ───────────────────────────────────────────
        violations = []
        encroaching = []
        threats: List[TreeThreat] = []
        min_clearance = 999.0

        for pt in canopy:
            if pt.classification not in ("tree", "shrub"):
                continue
            clearance = pt.distance_to_conductor_m
            min_clearance = min(min_clearance, clearance)
            deficit = nerc_min - clearance    # positive = violation

            sp = SPECIES_RISK.get(pt.species_guess, SPECIES_RISK["unknown"])
            growth = sp["growth"] * random.gauss(1.0, 0.15)

            if deficit > 0:
                violations.append(pt)
                years_to_viol = None  # already violated
            elif clearance < nerc_min * 2:
                encroaching.append(pt)
                years_to_viol = deficit / -growth if growth > 0 else None
            else:
                continue

            threat_score = self._tree_threat_score(
                clearance, nerc_min, growth, sp, deficit
            )

            threats.append(TreeThreat(
                lat=pt.lat, lon=pt.lon,
                height_m=pt.height_m,
                species=pt.species_guess,
                distance_to_conductor_m=round(clearance, 2),
                nerc_min_clearance_m=nerc_min,
                clearance_deficit_m=round(-deficit, 2),
                growth_rate_m_yr=round(growth, 2),
                years_to_violation=round(years_to_viol, 1) if years_to_viol else None,
                fire_risk=sp["fire"],
                failure_risk=sp["failure"],
                threat_score=round(threat_score, 1),
            ))

        # Sort threats by score descending
        threats.sort(key=lambda t: t.threat_score, reverse=True)

        # ── 2. Growth trend ─────────────────────────────────────────────────
        growth_trend = 0.0
        trend_label = "stable"
        if historical_surveys and len(historical_surveys) >= 2:
            growth_trend, trend_label = self._compute_growth_trend(
                historical_surveys + [current_survey]
            )

        # ── 3. Fire weather ─────────────────────────────────────────────────
        weather = self._fire_weather.get_conditions(mid_lat, mid_lon)
        fire_mult = self._fire_weather.risk_multiplier(weather)

        # ── 4. Dominant species ─────────────────────────────────────────────
        species_counts: Dict[str, int] = {}
        for pt in canopy:
            species_counts[pt.species_guess] = species_counts.get(pt.species_guess, 0) + 1
        dominant_species = max(species_counts, key=species_counts.get) if species_counts else "unknown"
        dom_risk = SPECIES_RISK.get(dominant_species, SPECIES_RISK["unknown"])

        # ── 5. Average growth rate ──────────────────────────────────────────
        avg_growth = dom_risk["growth"] * random.gauss(1.0, 0.1)

        # ── 6. Terrain multiplier ───────────────────────────────────────────
        terrain_mult = self._terrain_multiplier(span)

        # ── 7. Years to next violation ──────────────────────────────────────
        years_to_next = None
        future_threats = [t for t in threats if t.years_to_violation is not None]
        if future_threats:
            years_to_next = min(t.years_to_violation for t in future_threats)

        # ── 8. Last trim ────────────────────────────────────────────────────
        last_trim = self._trim_history.get(span.span_id)
        trim_days_ago = (datetime.now(timezone.utc) - last_trim).days if last_trim else None

        # ── 9. Canopy cover ─────────────────────────────────────────────────
        corridor_area_m2 = span.length_m * span.right_of_way_width_m * 2
        canopy_area = len([p for p in canopy if p.height_m > 2]) * 1.0  # ~1m² per return
        canopy_pct = min(100.0, (canopy_area / max(1, corridor_area_m2)) * 100)

        # ── 10. Overall risk score (0–100) ──────────────────────────────────
        score = self._overall_score(
            n_violations=len(violations),
            n_encroaching=len(encroaching),
            min_clearance=min_clearance if min_clearance < 999 else 99,
            nerc_min=nerc_min,
            growth_trend=growth_trend,
            fire_mult=fire_mult,
            terrain_mult=terrain_mult,
            dom_fire_risk=dom_risk["fire"],
            trim_days_ago=trim_days_ago,
        )

        risk_level = (
            "critical" if score >= 80 else
            "high"     if score >= 60 else
            "medium"   if score >= 35 else
            "low"
        )

        action, priority = self._recommend(score, len(violations), years_to_next, weather)

        fire_score = min(100.0, dom_risk["fire"] * 100 * fire_mult)

        return VegetationRiskScore(
            span_id=span.span_id,
            line_name=span.line_name,
            voltage_kv=span.voltage_kv,
            survey_date=current_survey.survey_date,
            overall_risk_score=round(score, 1),
            risk_level=risk_level,
            nerc_min_clearance_m=nerc_min,
            min_clearance_observed_m=round(min_clearance if min_clearance < 999 else 99, 2),
            clearance_violations=len(violations),
            encroaching_trees=len(encroaching),
            total_trees_in_corridor=len(canopy),
            canopy_cover_pct=round(canopy_pct, 1),
            growth_rate_m_yr=round(avg_growth, 2),
            years_to_next_violation=round(years_to_next, 1) if years_to_next else None,
            dominant_species=dominant_species,
            fire_risk_score=round(fire_score, 1),
            terrain_risk_multiplier=terrain_mult,
            last_trim_days_ago=trim_days_ago,
            recommended_action=action,
            work_order_priority=priority,
            threats=threats[:10],  # top 10 worst trees
            trend=trend_label,
            growth_trend_m_yr=round(growth_trend, 3),
        )

    def _tree_threat_score(
        self, clearance: float, nerc_min: float,
        growth: float, sp: Dict, deficit: float,
    ) -> float:
        """0–100 threat score for a single tree."""
        score = 0.0
        # Clearance component (0–50)
        if deficit > 0:
            score += 50 + min(30, deficit * 10)
        else:
            ratio = 1 - (clearance / (nerc_min * 2))
            score += max(0, ratio * 50)
        # Growth rate (0–20)
        score += min(20, growth * 8)
        # Fire risk (0–15)
        score += sp["fire"] * 15
        # Failure/structural risk (0–15)
        score += sp["failure"] * 15
        return min(100.0, score)

    def _compute_growth_trend(
        self, surveys: List[SpanLiDARSurvey]
    ) -> Tuple[float, str]:
        """
        Linear regression on median canopy height across survey years.
        Returns (m/year growth rate, trend label).
        """
        if len(surveys) < 2:
            return 0.0, "stable"

        heights = []
        for s in surveys:
            if s.canopy_points:
                median_h = sorted([p.height_m for p in s.canopy_points])[
                    len(s.canopy_points) // 2
                ]
                heights.append(median_h)

        if len(heights) < 2:
            return 0.0, "stable"

        # Simple slope calculation
        n = len(heights)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(heights) / n
        slope = (sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, heights)) /
                 max(0.001, sum((x - x_mean) ** 2 for x in xs)))

        trend = "worsening" if slope > 0.3 else "improving" if slope < -0.1 else "stable"
        return slope, trend

    def _terrain_multiplier(self, span: TransmissionSpan) -> float:
        """
        Steeper terrain → trees more likely to lean toward wires.
        Uses elevation difference between span endpoints as proxy for slope.
        """
        elev_diff = abs(span.start.elevation_m - span.end.elevation_m)
        slope_deg = math.degrees(math.atan2(elev_diff, span.length_m))
        if slope_deg < 5:   return 1.0
        elif slope_deg < 15: return 1.15
        elif slope_deg < 25: return 1.35
        else:                return 1.55

    def _overall_score(
        self, n_violations: int, n_encroaching: int, min_clearance: float,
        nerc_min: float, growth_trend: float, fire_mult: float,
        terrain_mult: float, dom_fire_risk: float, trim_days_ago: Optional[int],
    ) -> float:
        score = 0.0
        # NERC violation component (0–40): most important
        if n_violations > 0:
            score += min(40, 25 + n_violations * 8)
        else:
            deficit_ratio = max(0, 1 - min_clearance / (nerc_min * 1.5))
            score += deficit_ratio * 30

        # Encroachment density (0–20)
        score += min(20, n_encroaching * 2.5)

        # Growth trend (0–15)
        score += min(15, max(0, growth_trend * 12))

        # Fire risk overlay (0–15)
        score += dom_fire_risk * 15 * (fire_mult - 1.0)

        # Terrain (0–5)
        score += (terrain_mult - 1.0) * 10

        # Trim overdue penalty (0–10)
        if trim_days_ago and trim_days_ago > 365:
            score += min(10, (trim_days_ago - 365) / 100)

        return min(100.0, score)

    def _recommend(
        self, score: float, violations: int,
        years_to_next: Optional[float], weather: Dict,
    ) -> Tuple[str, str]:
        if violations > 0 or score >= 80:
            action = (
                "NERC FAC-003 violation — emergency trim required. "
                f"{violations} tree(s) below minimum clearance."
                + (" RED FLAG conditions active — elevated fire risk." if weather["red_flag"] else "")
            )
            return action, "immediate"

        elif score >= 60 or (years_to_next and years_to_next < 1):
            action = (
                f"High encroachment risk. Estimated violation in "
                f"{years_to_next:.1f} years. Schedule trim within 30 days."
                if years_to_next else
                "High encroachment — schedule trim within 30 days."
            )
            return action, "30_days"

        elif score >= 35 or (years_to_next and years_to_next < 3):
            action = (
                f"Moderate risk. Canopy encroaching — schedule trim within 90 days."
                f" Dominant species: {weather.get('station_id', '')}."
            )
            return action, "90_days"

        else:
            return "Within safe clearance margins. Standard annual inspection cycle.", "annual"

    def record_trim(self, span_id: str, trim_date: Optional[datetime] = None) -> None:
        """Record a vegetation trim work order completion."""
        self._trim_history[span_id] = trim_date or datetime.now(timezone.utc)
        logger.info(f"[VegEngine] Trim recorded for span {span_id}")


# ── Batch scoring ─────────────────────────────────────────────────────────────

class VegetationRiskBatchScorer:
    """
    Scores all spans in a transmission line or zone.
    Runs asynchronously and emits results to the event bus.
    """

    def __init__(self):
        self._engine = VegetationRiskEngine()

    async def score_all_spans(
        self, spans: List[TransmissionSpan], include_history: bool = True
    ) -> List[VegetationRiskScore]:
        """Score all spans, sorted by risk score descending."""
        import asyncio
        results = []
        for span in spans:
            try:
                survey = await lidar_manager.get_survey(span)
                history = None
                if include_history:
                    history = await lidar_manager.get_historical_surveys(span, years=3)

                score = self._engine.score_span(span, survey, history)
                results.append(score)
            except Exception as exc:
                logger.error(f"[BatchScorer] Failed to score span {span.span_id}: {exc}")

        results.sort(key=lambda r: r.overall_risk_score, reverse=True)
        return results

    def summary_stats(self, scores: List[VegetationRiskScore]) -> Dict[str, Any]:
        """Portfolio-level summary for the dashboard KPI cards."""
        if not scores:
            return {}
        return {
            "total_spans":           len(scores),
            "critical":              sum(1 for s in scores if s.risk_level == "critical"),
            "high":                  sum(1 for s in scores if s.risk_level == "high"),
            "medium":                sum(1 for s in scores if s.risk_level == "medium"),
            "low":                   sum(1 for s in scores if s.risk_level == "low"),
            "nerc_violations":       sum(s.clearance_violations for s in scores),
            "immediate_work_orders": sum(1 for s in scores if s.work_order_priority == "immediate"),
            "avg_risk_score":        round(sum(s.overall_risk_score for s in scores) / len(scores), 1),
            "highest_risk_span":     max(scores, key=lambda s: s.overall_risk_score).span_id,
            "total_encroaching":     sum(s.encroaching_trees for s in scores),
            "red_flag_spans":        sum(1 for s in scores if s.fire_risk_score > 70),
        }


# ── Singletons ────────────────────────────────────────────────────────────────
risk_engine = VegetationRiskEngine()
batch_scorer = VegetationRiskBatchScorer()
