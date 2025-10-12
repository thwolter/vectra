import pytest
from tenauth.schemas import AccessContext

from app.api.file import TemporaryUploadFile
from app.metadata.schemas import FinanceReportHints
from app.repositories import EmbeddingsRepository, JobRepository
from app.schemas.enums import CollectionEnum
from app.schemas.upload import ContinueProcessingInput, JobStatus, StartUploadInput
from app.services.factory import get_job_service


@pytest.fixture
async def job_uploaded(session, apple_report_first_page_upload, upload_service):
    file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    service = upload_service

    hints = FinanceReportHints(company='Acme Corp', document_type='10-K', financial_year=2024)
    init = await service.initiate_document_intake(session, payload=StartUploadInput(file=file, hints=hints))
    await service.continue_processing(
        payload=ContinueProcessingInput(
            hints=hints,
            job_id=init.job_id,
            document_id=init.document_id,
            digest=init.digest,
            file=file,
            access_context=AccessContext.from_session(session).model_dump(),
        ),
    )
    yield init, file
    await JobRepository.delete(session, job_id=init.job_id)


@pytest.mark.needs_postgres
async def test_init_upload_end_to_end_uses_database(session, job_uploaded):
    init, file = job_uploaded

    # Assert job completed
    job_service = get_job_service()
    status = await job_service.get_status(session=session, job_id=init.job_id)
    assert status.status == JobStatus.COMPLETED, f'Background job failed at: {status.progress.step}'
    assert status.progress.percent == 100

    # Assert database has embeddings for the source (exists by source)
    digest = await file.sha256_b64()
    exists = await EmbeddingsRepository.exists(session, digest=digest, collection=CollectionEnum.DEFAULT.value)
    assert exists, 'Expected embeddings to exist in DB for the uploaded document'

    # Assert embeddings metadata contains the enriched finance report fields
    all_md = await EmbeddingsRepository.get_metadata(session, digest=digest, collection=CollectionEnum.DEFAULT.value)
    assert all_md, 'Expected to retrieve embeddings metadata for the uploaded document'

    # Every chunk should have the same document-level metadata applied
    for md in all_md:
        assert md.get('digest') == digest
        assert md.get('company') == 'Acme Corp'
        assert md.get('document_type') == '10-K'
        assert md.get('financial_year') == 2024
