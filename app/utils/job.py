from __future__ import annotations

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

    return JobCtx(
        job_id=payload.job_id,
        tenant_id=payload.access_context.tenant_id,
        collection=collection,
        file=payload.file,
        digest=payload.digest,
        document_id=payload.document_id,
    )
