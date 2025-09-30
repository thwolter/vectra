from __future__ import annotations

from opentelemetry import metrics

# Create a meter for this module. The service.name is provided via OTEL_RESOURCE_ATTRIBUTES
meter = metrics.get_meter(__name__)

# OpenTelemetry instruments (exported names kept stable for minimal code changes)
# - Use Counter for monotonically increasing counts
# - Use UpDownCounter where we previously used Gauge with +/- adjustments
# - Use Histogram for duration measurements

TASKS_ENQUEUED_TOTAL = meter.create_counter(
    name="dramatiq_tasks_enqueued_total",
    description="Total number of Dramatiq tasks enqueued.",
)

TASKS_IN_PROGRESS = meter.create_up_down_counter(
    name="dramatiq_tasks_in_progress",
    description="Current number of Dramatiq tasks being processed.",
)

TASKS_QUEUE_DEPTH = meter.create_up_down_counter(
    name="dramatiq_tasks_queue_depth",
    description="Approximate number of Dramatiq tasks queued.",
)

TASKS_PROCESSED_TOTAL = meter.create_counter(
    name="dramatiq_tasks_processed_total",
    description="Total number of Dramatiq tasks processed.",
)

TASK_DURATION_SECONDS = meter.create_histogram(
    name="dramatiq_task_duration_seconds",
    description="Histogram of Dramatiq task execution duration in seconds.",
    unit="s",
)

ALERTS_TOTAL = meter.create_counter(
    name="dramatiq_alerts_total",
    description="Total number of Dramatiq alerts emitted.",
)
