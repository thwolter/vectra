from __future__ import annotations

from app.schemas.enums import CollectionEnum
from app.schemas.upload import ContinueProcessingInput
from app.schemas.jobs import JobCtx
from app.metadata.schemas import NoopHints


def build_job_ctx(
    *,
    upload_input: ContinueProcessingInput,
    collection: CollectionEnum,
) -> JobCtx:
    """Build a JobCtx from ContinueProcessingInput and a temporary path.

    This centralizes context construction and keeps continue_processing clean
    while avoiding import cycles at module import time.
    """

    if upload_input.hints is None:
        upload_input.hints = NoopHints()

    return JobCtx(
        job_id=upload_input.job_id,
        collection=collection,
        file=upload_input.file,
        hints=upload_input.hints,
        digest=upload_input.digest,
        document_id=upload_input.document_id,
    )
