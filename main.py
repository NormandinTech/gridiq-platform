"""
GridIQ — Internal Event Bus
Redis pub/sub based event bus connecting all platform modules in real time.
Every telemetry reading, alert, and threat event flows through here.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    # Telemetry
    TELEMETRY_READING       = "telemetry.reading"
    TELEMETRY_BATCH         = "telemetry.batch"

    # Alerts
    ALERT_CREATED           = "alert.created"
    ALERT_ACKNOWLEDGED      = "alert.acknowledged"
    ALERT_RESOLVED          = "alert.resolved"
    ALERT_ESCALATED         = "alert.escalated"

    # Asset
    ASSET_HEALTH_UPDATE     = "asset.health_update"
    ASSET_MAINTENANCE_DUE   = "asset.maintenance_due"
    ASSET_OFFLINE           = "asset.offline"
    ASSET_ONLINE            = "asset.online"

    # Grid
    GRID_TOPOLOGY_CHANGE    = "grid.topology_change"
    GRID_FREQUENCY_ANOMALY  = "grid.frequency_anomaly"
    GRID_OVERLOAD           = "grid.overload"

    # Forecast
    FORECAST_DEMAND_READY   = "forecast.demand_ready"
    FORECAST_RENEWABLE_READY = "forecast.renewable_ready"

    # Anomaly / AI
    ANOMALY_DETECTED        = "anomaly.detected"
    AI_RECOMMENDATION       = "ai.recommendation"

    # Security
    THREAT_DETECTED         = "security.threat_detected"
    THREAT_BLOCKED          = "security.threat_blocked"
    AUTH_FAILURE            = "security.auth_failure"
    COMPLIANCE_VIOLATION    = "security.compliance_violation"

    # Commands (control plane)
    COMMAND_DISPATCH        = "command.dispatch"
    COMMAND_ACK             = "command.ack"
    COMMAND_REJECT          = "command.reject"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]
    source: str = "gridiq-backend"
    event_id: str = ""
    timestamp: str = ""
    correlation_id: Optional[str] = None

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        d = asdict(self)
        d["type"] = self.type.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, raw: str) -> "Event":
        d = json.loads(raw)
        d["type"] = EventType(d["type"])
        return cls(**d)


# ── In-process event bus (works without Redis for dev/testing) ─────────────────

class InMemoryEventBus:
    """
    Lightweight in-process event bus for development and testing.
    In production, replace with RedisEventBus below.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._wildcard_subscribers: List[Callable] = []
        self._history: List[Event] = []
        self._max_history = 1000

    async def publish(self, event: Event) -> None:
        logger.debug(f"[EventBus] publish {event.type.value} id={event.event_id}")
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Notify type-specific subscribers
        for handler in self._subscribers.get(event.type.value, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error(f"[EventBus] handler error for {event.type.value}: {exc}")

        # Notify wildcard subscribers
        for handler in self._wildcard_subscribers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error(f"[EventBus] wildcard handler error: {exc}")

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(handler)
        logger.debug(f"[EventBus] subscribed to {key}")

    def subscribe_all(self, handler: Callable) -> None:
        self._wildcard_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        key = event_type.value
        if key in self._subscribers:
            self._subscribers[key] = [h for h in self._subscribers[key] if h != handler]

    def get_recent(self, event_type: Optional[EventType] = None, limit: int = 50) -> List[Event]:
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]


# ── Redis-backed event bus (production) ───────────────────────────────────────

class RedisEventBus:
    """
    Production event bus backed by Redis pub/sub + streams.
    Provides persistence, replay, and multi-process fan-out.
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None
        self._subscribers: Dict[str, List[Callable]] = {}
        self._listening = False

    async def connect(self):
        import redis.asyncio as aioredis
        self._redis = await aioredis.from_url(self.redis_url, decode_responses=True)
        logger.info("[RedisEventBus] connected")

    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()

    async def publish(self, event: Event) -> None:
        if not self._redis:
            logger.warning("[RedisEventBus] not connected, dropping event")
            return
        channel = f"gridiq:{event.type.value}"
        await self._redis.publish(channel, event.to_json())
        # Also append to stream for persistence + replay
        stream_key = f"gridiq:stream:{event.type.value.split('.')[0]}"
        await self._redis.xadd(stream_key, {"data": event.to_json()}, maxlen=10000)

    async def subscribe(self, event_type: EventType, handler: Callable) -> None:
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(handler)

    async def listen(self) -> None:
        """Start listening on all subscribed channels. Run as background task."""
        if not self._redis:
            return
        pubsub = self._redis.pubsub()
        channels = [f"gridiq:{k}" for k in self._subscribers]
        if not channels:
            return
        await pubsub.subscribe(*channels)
        self._listening = True
        logger.info(f"[RedisEventBus] listening on {len(channels)} channels")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event = Event.from_json(message["data"])
                    for handler in self._subscribers.get(event.type.value, []):
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                except Exception as exc:
                    logger.error(f"[RedisEventBus] message handling error: {exc}")


# ── Singleton ─────────────────────────────────────────────────────────────────

_bus: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    global _bus
    if _bus is None:
        _bus = InMemoryEventBus()
    return _bus


# ── Convenience publisher ─────────────────────────────────────────────────────

async def emit(event_type: EventType, payload: Dict[str, Any], source: str = "gridiq-backend") -> None:
    bus = get_event_bus()
    event = Event(type=event_type, payload=payload, source=source)
    await bus.publish(event)
