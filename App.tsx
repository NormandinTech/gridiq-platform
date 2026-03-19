"""
GridIQ — Telemetry Polling Service
Orchestrates all SCADA protocol adapters.
Polls each asset on its configured interval and feeds readings into the pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.protocols.adapters import BaseProtocolAdapter, create_adapter
from backend.services.asset_service import ingestion_service
from backend.core.event_bus import EventType, emit

logger = logging.getLogger(__name__)


class PollingJob:
    """Wraps a single asset's adapter and its polling schedule."""

    def __init__(self, asset_id: str, asset_tag: str, asset_type: str,
                 adapter: BaseProtocolAdapter, interval_sec: int = 30):
        self.asset_id = asset_id
        self.asset_tag = asset_tag
        self.asset_type = asset_type
        self.adapter = adapter
        self.interval_sec = interval_sec
        self._last_poll: Optional[datetime] = None
        self._consecutive_errors = 0

    async def poll(self) -> Optional[Dict]:
        reading = await self.adapter.safe_read()
        self._last_poll = datetime.now(timezone.utc)

        if reading.error:
            self._consecutive_errors += 1
            if self._consecutive_errors >= 3:
                await emit(EventType.ASSET_OFFLINE, {
                    "asset_id": self.asset_id,
                    "error": reading.error,
                    "consecutive_errors": self._consecutive_errors,
                })
            return None

        self._consecutive_errors = 0

        # Build normalized dict for ingestion pipeline
        return {
            "asset_id": self.asset_id,
            "asset_tag": self.asset_tag,
            "asset_type": self.asset_type,
            "timestamp": reading.timestamp.isoformat(),
            "active_power_mw": reading.active_power_mw,
            "reactive_power_mvar": reading.reactive_power_mvar,
            "voltage_kv": reading.voltage_kv,
            "current_amps": reading.current_amps,
            "frequency_hz": reading.frequency_hz,
            "temperature_c": reading.temperature_c,
            "oil_temperature_c": reading.oil_temperature_c,
            "status_raw": reading.status_raw,
            "extra": reading.extra,
            "read_latency_ms": reading.read_latency_ms,
        }


class TelemetryPollingService:
    """
    Manages all asset polling jobs.
    Each asset polls at its own interval (default 30s, critical assets 10s).
    Readings are batched and sent to the ingestion pipeline every cycle.
    """

    def __init__(self):
        self._jobs: Dict[str, PollingJob] = {}
        self._running = False
        self._poll_cycle_sec = 10  # How often to run the main loop

    def register_asset(self, asset_id: str, asset_tag: str, asset_type: str,
                       protocol: str, ip_address: str, port: int,
                       interval_sec: int = 30, **kwargs) -> None:
        """Register an asset for polling."""
        try:
            adapter = create_adapter(
                asset_id=asset_id,
                asset_tag=asset_tag,
                protocol=protocol,
                ip_address=ip_address,
                port=port,
                **kwargs,
            )
            self._jobs[asset_id] = PollingJob(
                asset_id=asset_id,
                asset_tag=asset_tag,
                asset_type=asset_type,
                adapter=adapter,
                interval_sec=interval_sec,
            )
            logger.info(f"[Polling] Registered {asset_tag} ({protocol}) @ {interval_sec}s")
        except Exception as exc:
            logger.error(f"[Polling] Failed to register {asset_tag}: {exc}")

    def register_from_config(self, assets: List[Dict]) -> None:
        """Bulk register assets from config/DB records."""
        for a in assets:
            if not a.get("protocol") or not a.get("ip_address"):
                continue
            self.register_asset(
                asset_id=a["id"],
                asset_tag=a["asset_tag"],
                asset_type=a["asset_type"],
                protocol=a["protocol"],
                ip_address=a["ip_address"],
                port=a.get("port", 502),
                interval_sec=a.get("polling_interval_sec", 30),
            )
        logger.info(f"[Polling] Registered {len(self._jobs)} assets from config")

    async def run(self) -> None:
        """Main polling loop. Run as a background asyncio task."""
        self._running = True
        logger.info(f"[Polling] Service started — {len(self._jobs)} assets")

        while self._running:
            now = datetime.now(timezone.utc)
            due_jobs = [
                job for job in self._jobs.values()
                if job._last_poll is None or
                (now - job._last_poll).total_seconds() >= job.interval_sec
            ]

            if due_jobs:
                # Poll all due assets concurrently
                results = await asyncio.gather(
                    *[job.poll() for job in due_jobs],
                    return_exceptions=True,
                )

                batch = [
                    r for r in results
                    if isinstance(r, dict) and r is not None
                ]

                if batch:
                    # Send to ingestion pipeline
                    stats = await ingestion_service.process_batch(batch)
                    logger.debug(
                        f"[Polling] Batch processed: {stats['stored']} stored, "
                        f"{stats['anomalies']} anomalies, {stats['errors']} errors"
                    )

                    # Broadcast to WebSocket clients via event bus
                    await emit(EventType.TELEMETRY_BATCH, {
                        "readings": batch,
                        "count": len(batch),
                    })

            await asyncio.sleep(self._poll_cycle_sec)

    def stop(self) -> None:
        self._running = False
        logger.info("[Polling] Service stopped")

    @property
    def stats(self) -> Dict:
        return {
            "total_assets": len(self._jobs),
            "running": self._running,
            "assets": [
                {
                    "asset_id": j.asset_id,
                    "asset_tag": j.asset_tag,
                    "interval_sec": j.interval_sec,
                    "last_poll": j._last_poll.isoformat() if j._last_poll else None,
                    "consecutive_errors": j._consecutive_errors,
                }
                for j in self._jobs.values()
            ],
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
polling_service = TelemetryPollingService()
