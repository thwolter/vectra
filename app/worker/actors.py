from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
import dramatiq
from loguru import logger
from redis import Redis
from app.core.config import get_settings
from app.schemas.upload import ContinueProcessingInput
from app.services.factory import get_upload_service
from .broker import broker  # noqa: F401  Ensures broker is configured
from app.core.observability import init_otel_worker, get_tracer

settings = get_settings()

# Initialise OpenTelemetry for the Dramatiq worker process (distinct service from the web app)
init_otel_worker(
    service_name=settings.service_name_worker,
    service_namespace=settings.service_namespace,
    deployment_environment=settings.deployment_env,
)
logger.bind(component="worker").info("WORKER_STARTUP: OpenTelemetry initialised and worker booting")

# Optional liveness heartbeat (visible to the web app via Redis keys)
def _start_heartbeat() -> None:
    redis_url = settings.redis_url.get_secret_value()
    if not redis_url:
        logger.bind(component="worker").info("WORKER_HEARTBEAT: REDIS_URL not set; skipping liveness beacons")
        return
    try:
        client = Redis.from_url(redis_url)
    except Exception as e:  # pragma: no cover - defensive
        logger.bind(component="worker").warning("WORKER_HEARTBEAT: failed to init Redis client: {}", e)
        return

    host = socket.gethostname()
    pid = os.getpid()
    key = f"worker:{host}:{pid}"

    def _beat() -> None:
        while True:
            try:
                client.setex(key, settings.worker_heartbeat_ttl, "alive")
            except Exception as ex:  # pragma: no cover - defensive
                logger.bind(component="worker").warning("WORKER_HEARTBEAT: setex failed: {}", ex)
            time.sleep(settings.worker_heartbeat_interval)

    threading.Thread(target=_beat, name="worker-heartbeat", daemon=True).start()

_start_heartbeat()




def _run_pipeline(payload: dict) -> None:
    tracer = get_tracer("dramatiq.upload")
    with tracer.start_as_current_span("prepare_payload"):
        parsed_payload = ContinueProcessingInput.from_message(payload)
    with tracer.start_as_current_span("process_upload_message"):
        upload_service = get_upload_service()
        logger.bind(component="worker").info("WORKER_MESSAGE: processing upload job {}", parsed_payload.job_id)
        asyncio.run(upload_service.continue_processing(payload=parsed_payload))


@dramatiq.actor(
    queue_name=settings.dramatiq_queue_name,
    time_limit=settings.dramatiq_time_limit_ms,
    max_retries=settings.dramatiq_max_retries,
)
def process_upload(payload: dict) -> None:
    """Execute the asynchronous upload pipeline inside a Dramatiq worker."""
    _run_pipeline(payload)
