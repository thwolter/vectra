from __future__ import annotations

from app.metadata.schemas import NoopHints
from app.schemas.jobs import JobCtx
from app.schemas.upload import ContinueProcessingInput


def build_job_ctx(
    *,
    payload: ContinueProcessingInput,
    collection: str,
) -> JobCtx:
    """Build a JobCtx from ContinueProcessingInput and a temporary path.

    This centralizes context construction and keeps continue_processing clean
    while avoiding import cycles at module import time.
    """

    if payload.hints is None:
        payload.hints = NoopHints()

    return JobCtx(
        job_id=payload.job_id,
        collection=collection,
        file=payload.file,
        hints=payload.hints,
        digest=payload.digest,
        document_id=payload.document_id,
    )
