from __future__ import annotations

import asyncio

import dramatiq
from loguru import logger

from app.core.config import get_settings
from app.schemas.upload import ContinueProcessingInput
from app.services.factory import get_upload_service
from app.worker.broker import broker  # noqa: F401  Ensures broker is configured

settings = get_settings()


def _run_pipeline(payload: dict) -> None:
    upload_service = get_upload_service()
    parsed_payload = ContinueProcessingInput.from_message(payload)

    logger.info('Processing upload job %s via Dramatiq', parsed_payload.job_id)
    asyncio.run(upload_service.continue_processing(payload=parsed_payload))


@dramatiq.actor(
    queue_name=settings.dramatiq_queue_name,
)
def process_upload(payload: dict) -> None:
    """Execute the asynchronous upload pipeline inside a Dramatiq worker."""

    _run_pipeline(payload)
