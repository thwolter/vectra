from __future__ import annotations

from loguru import logger

from core.config import get_settings
from schemas.upload import ContinueProcessingInput
from services.factory import get_upload_service
from worker.actors import process_upload


async def enqueue_upload_processing(payload: ContinueProcessingInput) -> None:
    """Dispatch upload processing to Dramatiq or run inline when no broker is set."""

    settings = get_settings()

    inline_fallback = getattr(process_upload, 'inline_fallback', False)

    if not settings.dramatiq_broker_url.get_secret_value() or inline_fallback:
        logger.debug('No Dramatiq broker configured; executing upload job %s inline.', payload.job_id)
        upload_service = get_upload_service()
        await upload_service.continue_processing(payload=payload)
        return

    message = payload.to_message()
    process_upload.send(message)
