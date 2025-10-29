from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import requests
from loguru import logger

from core.config import get_settings
from monitoring.metrics import ALERTS_TOTAL


class AlertManager:
    def __init__(self, *, webhook_url: str | None, enabled: bool) -> None:
        self._webhook_url = webhook_url
        self._enabled = enabled and bool(webhook_url)

    def notify_task_failure(self, *, actor: str, message: Any, exception: Exception) -> None:
        logger.error('Dramatiq task %s failed: %s', actor, exception)
        ALERTS_TOTAL.add(1, {'actor': actor, 'severity': 'error'})

        if not self._enabled or not self._webhook_url:
            return

        payload = {
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'actor': actor,
            'message_id': getattr(message, 'message_id', None),
            'payload': getattr(message, 'kwargs', {}),
            'exception': repr(exception),
        }

        try:
            requests.post(
                self._webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=5,
            )
        except Exception as send_exc:  # pragma: no cover - best effort
            logger.error('Failed to send alert webhook: %s', send_exc)


@lru_cache()
def get_alert_manager() -> AlertManager:
    settings = get_settings()
    webhook = settings.alerting_webhook_url.get_secret_value() if settings.alerting_webhook_url is not None else None
    return AlertManager(webhook_url=webhook, enabled=settings.monitoring_enabled)
