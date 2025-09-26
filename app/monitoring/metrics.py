from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

TASKS_ENQUEUED_TOTAL = Counter(
    'dramatiq_tasks_enqueued_total',
    'Total number of Dramatiq tasks enqueued.',
    ['actor'],
)
TASKS_IN_PROGRESS = Gauge(
    'dramatiq_tasks_in_progress',
    'Current number of Dramatiq tasks being processed.',
    ['actor'],
)
TASKS_QUEUE_DEPTH = Gauge(
    'dramatiq_tasks_queue_depth',
    'Approximate number of Dramatiq tasks queued.',
    ['actor'],
)
TASKS_PROCESSED_TOTAL = Counter(
    'dramatiq_tasks_processed_total',
    'Total number of Dramatiq tasks processed.',
    ['actor', 'status'],
)
TASK_DURATION_SECONDS = Histogram(
    'dramatiq_task_duration_seconds',
    'Histogram of Dramatiq task execution duration in seconds.',
    ['actor'],
)
ALERTS_TOTAL = Counter(
    'dramatiq_alerts_total',
    'Total number of Dramatiq alerts emitted.',
    ['actor', 'severity'],
)
