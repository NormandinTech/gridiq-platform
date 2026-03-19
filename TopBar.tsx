"""
GridIQ Vegetation Engine — Transmission Line Seed Data
=======================================================
Realistic Western US transmission corridors for dev/demo.
Spans are modeled after actual PG&E, SCE, and LADWP geography
(coordinates are approximate — not exact utility infrastructure).
"""
from __future__ import annotations

import math
import random
from typing import List

from backend.vegetation.lidar_ingest import GeoPoint, TransmissionSpan


def _interpolate_spans(
    line_id: str,
    line_name: str,
    start: GeoPoint,
    end: GeoPoint,
    n_spans: int,
    conductor_height_m: float,
    voltage_kv: float,
    row_width_m: float = 15.0,
    zone: str = "",
) -> List[TransmissionSpan]:
    """Divide a line segment into N individual spans."""
    spans = []
    for i in range(n_spans):
        t0 = i / n_spans
        t1 = (i + 1) / n_spans
        p0 = GeoPoint(
            lat=start.lat + t0 * (end.lat - start.lat),
            lon=start.lon + t0 * (end.lon - start.lon),
            elevation_m=start.elevation_m + t0 * (end.elevation_m - start.elevation_m),
        )
        p1 = GeoPoint(
            lat=start.lat + t1 * (end.lat - start.lat),
            lon=start.lon + t1 * (end.lon - start.lon),
            elevation_m=start.elevation_m + t1 * (end.elevation_m - start.elevation_m),
        )
        # Span length in meters (haversine approximation)
        dlat = math.radians(p1.lat - p0.lat)
        dlon = math.radians(p1.lon - p0.lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(p0.lat)) * math.cos(math.radians(p1.lat)) * math.sin(dlon/2)**2
        length_m = 2 * math.asin(math.sqrt(a)) * 6_371_000

        spans.append(TransmissionSpan(
            span_id=f"{line_id}-S{i+1:03d}",
            line_id=line_id,
            line_name=line_name,
            start=p0,
            end=p1,
            conductor_height_m=conductor_height_m + random.gauss(0, 0.5),
            voltage_kv=voltage_kv,
            length_m=round(length_m, 1),
            right_of_way_width_m=row_width_m,
            zone=zone,
        ))
    return spans


# ── Transmission line definitions ─────────────────────────────────────────────

TRANSMISSION_LINES = [
    # Northern California — Sierra Nevada foothills (high fire risk)
    dict(
        line_id="CA-230-SIERRA",
        line_name="Sierra Foothills 230kV",
        start=GeoPoint(38.82, -121.05, 320),
        end=GeoPoint(38.60, -120.78, 680),
        n_spans=18,
        conductor_height_m=12.5,
        voltage_kv=230,
        row_width_m=20,
        zone="North Zone",
    ),
    # Oakland Hills — dense urban-wildland interface
    dict(
        line_id="CA-115-OAKHILL",
        line_name="Oakland Hills 115kV",
        start=GeoPoint(37.86, -122.23, 180),
        end=GeoPoint(37.78, -122.18, 420),
        n_spans=12,
        conductor_height_m=10.0,
        voltage_kv=115,
        row_width_m=15,
        zone="Central Zone",
    ),
    # Central Valley — agricultural flatlands (low terrain risk, eucalyptus windbreaks)
    dict(
        line_id="CA-500-VALLEY",
        line_name="Central Valley 500kV",
        start=GeoPoint(37.35, -121.0, 25),
        end=GeoPoint(37.10, -120.7, 30),
        n_spans=14,
        conductor_height_m=18.0,
        voltage_kv=500,
        row_width_m=30,
        zone="South Zone",
    ),
    # Santa Cruz Mountains — coastal redwood and mixed conifer (very high trees)
    dict(
        line_id="CA-115-SANTACRUZ",
        line_name="Santa Cruz Mountains 115kV",
        start=GeoPoint(37.22, -122.10, 280),
        end=GeoPoint(37.05, -121.95, 520),
        n_spans=10,
        conductor_height_m=11.0,
        voltage_kv=115,
        row_width_m=15,
        zone="Central Zone",
    ),
    # Diablo Range — dry chaparral and oak woodland
    dict(
        line_id="CA-230-DIABLO",
        line_name="Diablo Range 230kV",
        start=GeoPoint(37.65, -121.80, 450),
        end=GeoPoint(37.40, -121.55, 620),
        n_spans=16,
        conductor_height_m=13.0,
        voltage_kv=230,
        row_width_m=20,
        zone="Central Zone",
    ),
    # Sacramento River delta — willows and cottonwoods along waterways
    dict(
        line_id="CA-115-DELTA",
        line_name="Sacramento Delta 115kV",
        start=GeoPoint(38.05, -121.62, 2),
        end=GeoPoint(37.88, -121.42, 4),
        n_spans=8,
        conductor_height_m=10.5,
        voltage_kv=115,
        row_width_m=15,
        zone="North Zone",
    ),
]


def get_all_spans() -> List[TransmissionSpan]:
    """Return all transmission spans for demo/dev scoring."""
    all_spans = []
    for line_def in TRANSMISSION_LINES:
        spans = _interpolate_spans(**line_def)
        all_spans.extend(spans)
    return all_spans


def get_spans_by_zone(zone: str) -> List[TransmissionSpan]:
    return [s for s in get_all_spans() if s.zone == zone]


def get_spans_by_line(line_id: str) -> List[TransmissionSpan]:
    return [s for s in get_all_spans() if s.line_id == line_id]
