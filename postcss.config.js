"""
GridIQ — Asset Service
Business logic for asset management, health tracking, and maintenance scheduling.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.ml.engine import anomaly_detector, health_scorer
from backend.core.event_bus import EventType, emit

logger = logging.getLogger(__name__)


class AssetService:
    """
    Manages grid assets — CRUD, health scoring, status tracking.
    In production this talks to the DB via SQLAlchemy.
    Dev mode uses the in-memory mock from api/routes.py.
    """

    async def update_health_from_telemetry(
        self, asset_id: str, telemetry: Dict[str, Any]
    ) -> float:
        """
        Recompute health score from latest telemetry reading.
        Called by the telemetry ingestion pipeline on each batch.
        """
        asset_data = {
            "temperature_c": telemetry.get("temperature_c", 65),
            "fault_count_30d": telemetry.get("extra", {}).get("fault_count", 0),
            "maintenance_overdue": False,
            "anomaly_rate_7d": 0,
        }

        score = health_scorer.score(asset_data)

        # Check for anomaly on active power
        power = telemetry.get("active_power_mw")
        if power is not None:
            anomaly_score, is_anomaly = anomaly_detector.score(asset_id, power)
            if is_anomaly:
                await emit(EventType.ANOMALY_DETECTED, {
                    "asset_id": asset_id,
                    "metric": "active_power_mw",
                    "value": power,
                    "anomaly_score": anomaly_score,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                # Reduce health proportionally to anomaly severity
                score = max(0.0, score - (anomaly_score / 100) * 15)

        logger.debug(f"[AssetService] {asset_id} health={score:.1f}")
        return score

    async def check_maintenance_due(
        self, asset_id: str, health_score: float, asset_data: Dict
    ) -> Optional[Dict]:
        """
        Check if predictive maintenance should be triggered.
        Returns a maintenance record dict if action is needed, else None.
        """
        fail_prob = health_scorer.predict_failure_probability(health_score)

        if fail_prob > 0.25:
            priority = "urgent" if fail_prob > 0.40 else "high"
            record = {
                "asset_id": asset_id,
                "maintenance_type": "predictive",
                "priority": priority,
                "title": f"Predictive maintenance — health score {health_score:.0f}%",
                "failure_probability": fail_prob,
                "predicted_failure_date": (
                    datetime.now(timezone.utc) + timedelta(days=int(30 * (1 - fail_prob)))
                ).isoformat(),
                "status": "open",
            }
            await emit(EventType.ASSET_MAINTENANCE_DUE, record)
            return record

        return None

    async def handle_asset_offline(self, asset_id: str, last_seen: datetime) -> None:
        """Called when an asset stops responding to polling."""
        offline_minutes = (
            datetime.now(timezone.utc) - last_seen
        ).total_seconds() / 60

        if offline_minutes > 5:
            await emit(EventType.ASSET_OFFLINE, {
                "asset_id": asset_id,
                "offline_since": last_seen.isoformat(),
                "offline_minutes": round(offline_minutes, 1),
            })
            logger.warning(
                f"[AssetService] Asset {asset_id} offline for {offline_minutes:.0f} min"
            )


class TelemetryIngestionService:
    """
    Processes incoming telemetry batches from the protocol adapters.
    Pipeline: validate → store → analyze → alert → broadcast.
    """

    def __init__(self):
        self._asset_service = AssetService()
        self._reading_count = 0

    async def process_batch(self, readings: List[Dict[str, Any]]) -> Dict:
        """
        Process a batch of raw readings.
        Returns summary stats for monitoring.
        """
        stored = 0
        anomalies = 0
        errors = 0

        for reading in readings:
            try:
                asset_id = reading.get("asset_id")
                if not asset_id:
                    errors += 1
                    continue

                # Validate reading
                if not self._validate_reading(reading):
                    errors += 1
                    continue

                # Update asset health
                health = await self._asset_service.update_health_from_telemetry(
                    asset_id, reading
                )

                # Check for anomalies in frequency (grid-wide metric)
                freq = reading.get("frequency_hz")
                if freq is not None:
                    if abs(freq - 60.0) > 0.5:
                        await emit(EventType.GRID_FREQUENCY_ANOMALY, {
                            "asset_id": asset_id,
                            "frequency_hz": freq,
                            "deviation": abs(freq - 60.0),
                            "timestamp": reading.get("timestamp"),
                        })
                        anomalies += 1

                stored += 1
                self._reading_count += 1

            except Exception as exc:
                logger.error(f"[Ingestion] Error processing reading for {reading.get('asset_id')}: {exc}")
                errors += 1

        return {
            "processed": len(readings),
            "stored": stored,
            "anomalies": anomalies,
            "errors": errors,
            "total_readings": self._reading_count,
        }

    def _validate_reading(self, reading: Dict) -> bool:
        """Basic sanity checks on telemetry values."""
        # Voltage sanity (0 – 1000 kV)
        v = reading.get("voltage_kv")
        if v is not None and not (0 <= v <= 1000):
            logger.warning(f"[Ingestion] Suspicious voltage {v} kV for {reading.get('asset_id')}")
            return False

        # Frequency sanity (55 – 65 Hz for 60 Hz grid)
        f = reading.get("frequency_hz")
        if f is not None and not (55 <= f <= 65):
            logger.warning(f"[Ingestion] Out-of-range frequency {f} Hz for {reading.get('asset_id')}")
            return False

        return True


# ── Singletons ────────────────────────────────────────────────────────────────
asset_service = AssetService()
ingestion_service = TelemetryIngestionService()
