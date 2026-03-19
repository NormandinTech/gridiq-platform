"""
GridIQ — Alert Service
Manages alert lifecycle: creation, deduplication, escalation, notifications.
Integrates with the event bus to react to anomalies and thresholds.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.core.event_bus import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


# ── Alert severity thresholds ─────────────────────────────────────────────────

FREQUENCY_THRESHOLDS = {
    "critical": (59.3, 60.7),   # Hz — outside this = critical
    "high":     (59.5, 60.5),
    "medium":   (59.7, 60.3),
}

VOLTAGE_THRESHOLDS_PCT = {
    "critical": 15,   # >15% deviation from nominal = critical
    "high":     10,
    "medium":   5,
}

TEMPERATURE_THRESHOLDS_C = {
    "transformer": {"medium": 80, "high": 90, "critical": 100},
    "default":     {"medium": 75, "high": 85, "critical": 95},
}


class AlertService:
    """
    Creates, deduplicates, and manages operational alerts.
    In production connects to the PostgreSQL alerts table via SQLAlchemy.
    """

    def __init__(self):
        self._recent_alerts: Dict[str, datetime] = {}  # dedup key -> last_seen
        self._dedup_window_minutes = 15

    def _dedup_key(self, asset_id: Optional[str], title: str) -> str:
        return f"{asset_id or 'system'}:{title[:50]}"

    def _is_duplicate(self, key: str) -> bool:
        last = self._recent_alerts.get(key)
        if last is None:
            return False
        return (datetime.now(timezone.utc) - last).total_seconds() < self._dedup_window_minutes * 60

    async def create_alert(
        self,
        title: str,
        severity: str,
        description: str,
        asset_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        source: str = "system",
        category: str = "operational",
        confidence: Optional[float] = None,
        anomaly_score: Optional[float] = None,
        recommended_action: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Create a new alert. Returns None if deduplicated.
        """
        key = self._dedup_key(asset_id, title)
        if self._is_duplicate(key):
            logger.debug(f"[AlertService] Deduplicated alert: {title}")
            return None

        self._recent_alerts[key] = datetime.now(timezone.utc)

        alert = {
            "id": f"alert-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "asset_id": asset_id,
            "zone_id": zone_id,
            "severity": severity,
            "status": "open",
            "title": title,
            "description": description,
            "source": source,
            "category": category,
            "confidence": confidence,
            "anomaly_score": anomaly_score,
            "recommended_action": recommended_action,
            "metadata_json": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Emit to event bus
        bus = get_event_bus()
        from backend.core.event_bus import Event
        await bus.publish(Event(
            type=EventType.ALERT_CREATED,
            payload=alert,
            source="alert-service",
        ))

        logger.info(f"[AlertService] [{severity.upper()}] {title}")
        return alert

    async def evaluate_telemetry(
        self, asset_id: str, asset_type: str, reading: Dict[str, Any]
    ) -> List[Dict]:
        """
        Evaluate a telemetry reading against thresholds.
        Returns list of alerts created.
        """
        alerts = []

        # Frequency check
        freq = reading.get("frequency_hz")
        if freq is not None:
            for sev, (lo, hi) in FREQUENCY_THRESHOLDS.items():
                if not (lo <= freq <= hi):
                    alert = await self.create_alert(
                        title=f"Grid frequency deviation — {freq:.4f} Hz",
                        severity=sev,
                        description=(
                            f"Grid frequency {freq:.4f} Hz is outside {sev} threshold "
                            f"({lo}–{hi} Hz). Check generation-load balance."
                        ),
                        asset_id=asset_id,
                        source="threshold",
                        category="operational",
                        recommended_action="Check generation dispatch and load balance",
                    )
                    if alert:
                        alerts.append(alert)
                    break  # Only create highest severity

        # Temperature check
        temp = reading.get("temperature_c")
        if temp is not None:
            thresholds = TEMPERATURE_THRESHOLDS_C.get(asset_type, TEMPERATURE_THRESHOLDS_C["default"])
            for sev in ("critical", "high", "medium"):
                if temp >= thresholds[sev]:
                    alert = await self.create_alert(
                        title=f"High temperature — {temp:.1f}°C on {asset_id}",
                        severity=sev,
                        description=(
                            f"Asset temperature {temp:.1f}°C exceeds {sev} threshold "
                            f"({thresholds[sev]}°C). Risk of accelerated insulation degradation."
                        ),
                        asset_id=asset_id,
                        source="threshold",
                        category="maintenance",
                        recommended_action="Inspect cooling system and reduce load if possible",
                    )
                    if alert:
                        alerts.append(alert)
                    break

        return alerts

    async def escalate_stale_alerts(self, max_open_minutes: int = 60) -> List[str]:
        """
        Find alerts that have been open too long without acknowledgment
        and escalate them (notify SOC, increase severity).
        Returns list of escalated alert IDs.
        """
        # In production this queries the DB for open alerts older than threshold
        logger.info(f"[AlertService] Running escalation check (threshold={max_open_minutes}m)")
        return []


class NotificationService:
    """
    Sends alert notifications via email, Slack, PagerDuty.
    Triggered by the alert service on critical/high severity alerts.
    """

    async def send_email(self, recipients: List[str], subject: str, body: str) -> bool:
        """Send email alert via SMTP. Returns success flag."""
        try:
            from backend.core.config import settings
            import smtplib
            from email.mime.text import MIMEText

            if not settings.smtp_username:
                logger.debug("[Notifications] SMTP not configured — skipping email")
                return False

            msg = MIMEText(body, "html")
            msg["Subject"] = f"[GridIQ Alert] {subject}"
            msg["From"] = settings.smtp_username
            msg["To"] = ", ".join(recipients)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
                server.sendmail(settings.smtp_username, recipients, msg.as_string())

            logger.info(f"[Notifications] Email sent: {subject}")
            return True
        except Exception as exc:
            logger.error(f"[Notifications] Email failed: {exc}")
            return False

    async def send_slack(self, message: str, level: str = "warning") -> bool:
        """Post alert to Slack via webhook."""
        try:
            from backend.core.config import settings
            import json, urllib.request

            if not settings.slack_webhook_url:
                return False

            color = {"critical": "#dc2626", "high": "#f59e0b",
                     "medium": "#3b82f6", "low": "#22c55e"}.get(level, "#888")
            payload = {
                "attachments": [{
                    "color": color,
                    "text": message,
                    "footer": "GridIQ Platform",
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }]
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                settings.slack_webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception as exc:
            logger.error(f"[Notifications] Slack failed: {exc}")
            return False


# ── Event bus subscriptions ───────────────────────────────────────────────────

async def setup_alert_subscriptions() -> None:
    """
    Subscribe alert service to relevant event bus events.
    Called during application startup.
    """
    bus = get_event_bus()
    svc = AlertService()
    notif = NotificationService()

    async def on_anomaly(event: Event) -> None:
        p = event.payload
        await svc.create_alert(
            title=f"AI anomaly detected — {p.get('metric')} on {p.get('asset_id')}",
            severity="high" if p.get("anomaly_score", 0) > 85 else "medium",
            description=(
                f"Anomaly score {p.get('anomaly_score', 0):.1f}/100 on "
                f"{p.get('metric')} = {p.get('value')}."
            ),
            asset_id=p.get("asset_id"),
            source="ai",
            category="operational",
            confidence=p.get("anomaly_score", 0) / 100,
            anomaly_score=p.get("anomaly_score"),
        )

    async def on_critical_alert(event: Event) -> None:
        p = event.payload
        if p.get("severity") in ("critical", "high"):
            await notif.send_slack(
                f"*{p.get('severity', '').upper()}* — {p.get('title')}\n{p.get('description', '')}",
                level=p.get("severity", "high"),
            )

    bus.subscribe(EventType.ANOMALY_DETECTED, on_anomaly)
    bus.subscribe(EventType.ALERT_CREATED, on_critical_alert)
    logger.info("[AlertService] Event subscriptions registered")


# ── Singletons ────────────────────────────────────────────────────────────────
alert_service = AlertService()
notification_service = NotificationService()
