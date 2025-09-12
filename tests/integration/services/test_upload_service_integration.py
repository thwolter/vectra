from pathlib import Path

import pytest

from app.api.file import TemporaryUploadFile
from app.services.factory import get_job_service
from app.services.upload_service import UploadService
from app.schemas.enums import CollectionEnum
from app.schemas.upload import JobStatus
from app.metadata.schemas import NoopHints
from app.schemas.upload import StartUploadInput, ContinueProcessingInput
from app.store.local_store import LocalFileStore
from app.store.protocols import StoreProtocol
from app.repositories.embeddings import Embeddings


@pytest.fixture
def base_prefix(tmp_path) -> Path:
    return tmp_path / 'local-tests'


@pytest.mark.integration
@pytest.mark.asyncio
async def test_init_upload_end_to_end_uses_database(
    apple_report_first_page_upload, base_prefix, session
):
    store = LocalFileStore(CollectionEnum.DEFAULT, base_path=base_prefix)
    assert isinstance(store, StoreProtocol)

    service = UploadService(store=store)
    file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)

    init = await service.start_document_upload(
        session,
        payload=StartUploadInput(
            file=file,
            hints=NoopHints(),
        ),
    )

    await service.continue_processing(
        session=session,
        payload=ContinueProcessingInput(
            hints=NoopHints(),
            job_id=init.job_id,
            document_id=init.document_id,
            digest=init.digest,
            file=file,
        ),
    )

    # Assert job completed
    job_service = get_job_service()
    job = await job_service.get_status(session=session, job_id=init.job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.progress.percent == 100

    # Assert database has embeddings for the source (exists by source)
    digest = await file.sha256_b64()
    exists = await Embeddings.exists_by_digest(
        session, digest=digest, collection=CollectionEnum.DEFAULT.value
    )
    assert exists, 'Expected embeddings to exist in DB for the uploaded document'
