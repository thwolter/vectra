from __future__ import annotations

import time

from dramatiq.middleware import Middleware

from app.monitoring.alerting import get_alert_manager
from app.monitoring.metrics import (
    TASK_DURATION_SECONDS,
    TASKS_ENQUEUED_TOTAL,
    TASKS_IN_PROGRESS,
    TASKS_PROCESSED_TOTAL,
    TASKS_QUEUE_DEPTH,
)


class DramatiqMonitoringMiddleware(Middleware):
    """Collect Prometheus metrics and forward alerts for Dramatiq tasks."""

    _START_KEY = '__metrics_start_ts'

    def __init__(self) -> None:
        self._alert_manager = get_alert_manager()

    def before_enqueue(self, broker, message, delay=None):  # noqa: D401 - Dramatiq hook
        actor = message.actor_name
        TASKS_ENQUEUED_TOTAL.labels(actor=actor).inc()
        TASKS_QUEUE_DEPTH.labels(actor=actor).inc()

    def after_dequeue(self, broker, message):  # noqa: D401 - Dramatiq hook
        actor = message.actor_name
        TASKS_QUEUE_DEPTH.labels(actor=actor).dec()

    def before_process_message(self, broker, message):  # noqa: D401 - Dramatiq hook
        actor = message.actor_name
        TASKS_IN_PROGRESS.labels(actor=actor).inc()
        message.options[self._START_KEY] = time.perf_counter()

    def after_process_message(self, broker, message, *, result=None, exception=None):  # noqa: D401 - Dramatiq hook
        actor = message.actor_name
        TASKS_IN_PROGRESS.labels(actor=actor).dec()
        TASKS_PROCESSED_TOTAL.labels(actor=actor, status='success').inc()

        start = message.options.pop(self._START_KEY, None)
        if start is not None:
            duration = time.perf_counter() - start
            TASK_DURATION_SECONDS.labels(actor=actor).observe(duration)

    def after_process_message_failure(self, broker, message, exception):  # noqa: D401 - Dramatiq hook
        actor = message.actor_name
        TASKS_IN_PROGRESS.labels(actor=actor).dec()
        TASKS_PROCESSED_TOTAL.labels(actor=actor, status='failure').inc()
        self._alert_manager.notify_task_failure(actor=actor, message=message, exception=exception)
