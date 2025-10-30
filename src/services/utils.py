from __future__ import annotations

from schemas.jobs import JobCtx
from schemas.upload import ContinueProcessingInput, JobStatus


def normalise_progress(step, percent, status):
    if status == JobStatus.COMPLETED:
        return 100, ''

    norm_step = step or None
    norm_percent = None if percent is None else max(0, min(100, int(percent)))
    return norm_percent, norm_step


def build_job_ctx(
    *,
    payload: ContinueProcessingInput,
    collection: str,
) -> JobCtx:
    """Build a JobCtx from ContinueProcessingInput and a temporary path.

    This centralizes context construction and keeps continue_processing clean
    while avoiding import cycles at module import time.
    """

    return JobCtx(
        job_id=payload.job_id,
        tenant_id=payload.access_context.tenant_id,
        collection=collection,
        file=payload.file,
        digest=payload.digest,
        document_id=payload.document_id,
    )
