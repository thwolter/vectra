import io
import uuid

from fastapi import UploadFile
from langchain_core.documents import Document
from redis.asyncio import Redis
from starlette.datastructures import Headers
from tenauth.schemas import AccessContext

from api.file import TemporaryUploadFile
from core.config import get_settings
from schemas.upload import ContinueProcessingInput, JobStatus
from services.factory import get_upload_service


def _install_test_pipeline(monkeypatch):
    class _FakeParser:
        def __init__(self, *_, **__):
            self._docs = [Document(page_content='stub-chunk', metadata={})]

        async def parse(self, file: str):
            return list(self._docs)

        async def to_markdown(self) -> str:
            return 'stub-markdown'

    class _FakeEmbeddings:
        def __init__(self, *_, **__):
            self.dim = 1536

        async def aembed_documents(self, texts):
            return [[float((idx % 2))] * self.dim for idx, _ in enumerate(texts)]

        async def embed_query(self, text: str):
            return [0.0] * self.dim

    monkeypatch.setattr('services.upload_steps.LlamaParser', _FakeParser)
    monkeypatch.setattr('vector.factory.OpenAIEmbeddings', _FakeEmbeddings)


async def test_upload_creates_job_and_sends_to_worker(
    small_pdf,
    auth_session,
    auth_client,
):
    api_client = auth_client
    settings = get_settings()
    redis_url = settings.dramatiq_broker_url.get_secret_value()
    redis_queue_key = f'dramatiq:{settings.dramatiq_queue_name}'
    redis_client = Redis.from_url(redis_url)
    try:
        await redis_client.delete(redis_queue_key)

        with open(small_pdf, 'rb') as f:
            file_bytes = f.read()
        files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

        # Step 1: init upload via API
        r = await api_client.post('/api/v1/uploads', files=files)
        assert r.status_code == 201, r.text
        init = r.json()

        # Step 2: check job status via API
        r2 = await api_client.get(f'/api/v1/jobs/{init["job_id"]}')
        assert r2.status_code == 200
        status_payload = r2.json()
        # Status may vary depending on environment timing; ensure endpoint is reachable and job_id matches
        assert status_payload['job_id'] == init['job_id']

        # Step 3: ensure the Dramatiq worker message landed in Redis
        message_count: int = await redis_client.llen(redis_queue_key)  # type: ignore[not-async]
        assert message_count > 0, 'Expected upload job message to be queued in Redis'

    finally:
        await redis_client.delete(redis_queue_key)
        await redis_client.aclose()


async def test_second_upload_is_deduplicated_after_first_ingestion(
    apple_report_first_page,
    auth_client,
    auth_session,
    monkeypatch,
):
    _install_test_pipeline(monkeypatch)

    with open(apple_report_first_page, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # First upload + full processing via service
    r1 = await auth_client.post('/api/v1/uploads', files=files)
    assert r1.status_code == 201
    init1 = r1.json()

    upload_file = UploadFile(
        file=io.BytesIO(file_bytes),
        filename='tiny.pdf',
        headers=Headers({'content-type': 'application/pdf'}),
    )
    temp_file = TemporaryUploadFile.from_upload(upload_file)
    upload_service = get_upload_service()
    await upload_service.continue_processing(
        payload=ContinueProcessingInput(
            job_id=uuid.UUID(init1['job_id']),
            document_id=uuid.UUID(init1['document_id']),
            digest=init1['digest'],
            file=temp_file,
            access_context=AccessContext.from_session(auth_session),
        )
    )

    temp_file.close()

    # Second upload init should report deduplicated True
    r2 = await auth_client.post('/api/v1/uploads', files=files)
    assert r2.status_code == 201
    init2 = r2.json()
    assert init2['status'] == JobStatus.DUPLICATED.value
    assert init2['already_running'] is False
