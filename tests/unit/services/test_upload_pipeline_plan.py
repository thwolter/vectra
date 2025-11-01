from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.documents import Document

from repositories.schemas import IngestionVersion
from schemas.jobs import JobCtx
from services.upload_steps import UploadPipeline


class DummyStore:
    """Minimal store stub for UploadPipeline tests."""

    async def save_original(self, *args, **kwargs):  # pragma: no cover - not used in these tests
        raise AssertionError('save_original should not be called')

    async def save_markdown(self, *args, **kwargs):  # pragma: no cover - not used in these tests
        raise AssertionError('save_markdown should not be called')


def _build_ctx(*, plan, docs: list[Document] | None = None, existing_ingestion=None) -> JobCtx:
    file_stub = SimpleNamespace(filename='unit.pdf', content_type='application/pdf', path=Path(__file__))
    return JobCtx(
        job_id=uuid4(),
        tenant_id=uuid4(),
        collection='unit',
        file=file_stub,
        document_id=uuid4(),
        digest='digest',
        docs=list(docs or []),
        existing_ingestion=existing_ingestion,
        run_parser=plan.run_parser,
        run_chunker=plan.run_chunker,
        run_embedding=plan.run_embedding,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_skips_when_plan_matches(monkeypatch: pytest.MonkeyPatch):
    version = IngestionVersion(collection='c', parser_fp='p', chunker_fp='c', embedding_fp='e')
    record = SimpleNamespace(parser_fp='p', chunker_fp='c', embedding_fp='e')
    plan = version.plan_for(record)

    pipeline = UploadPipeline(store=DummyStore())

    async def fake_load_cached_markdown(self, ctx):
        return '# cached markdown', 'cached.md'

    monkeypatch.setattr(UploadPipeline, '_load_cached_markdown', fake_load_cached_markdown)

    class FailParser:
        def __init__(self, *args, **kwargs):
            raise AssertionError('Parser should not run when plan skips it')

    def fail_chunker(*args, **kwargs):
        raise AssertionError('Chunker should not run when plan skips it')

    class FailIngestor:
        def __init__(self, *args, **kwargs):
            raise AssertionError('Embedding should not run when plan skips it')

    async def fake_find(*args, **kwargs):
        return None

    async def fake_fetch(*args, **kwargs):
        return []

    async def fake_delete(*args, **kwargs):
        return None

    async def fake_job_update(*args, **kwargs):
        return None

    monkeypatch.setattr('services.upload_steps.LlamaParser', FailParser)
    monkeypatch.setattr('services.upload_steps.chunk_documents_by_headings', fail_chunker)
    monkeypatch.setattr('services.upload_steps.DocumentIngestor', FailIngestor)
    monkeypatch.setattr('services.upload_steps.ingestion_repository.find', fake_find)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.fetch_documents', fake_fetch)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.delete', fake_delete)
    monkeypatch.setattr('services.upload_steps.job_repository.update', fake_job_update)

    ctx = _build_ctx(plan=plan)

    ctx_after_parse = await pipeline.parse_document(ctx)
    assert ctx_after_parse.run_parser is False
    assert ctx_after_parse.markdown_text == '# cached markdown'
    assert ctx_after_parse.docs and isinstance(ctx_after_parse.docs[0], Document)

    ctx_after_chunk = await pipeline.chunk_documents(ctx_after_parse)
    assert ctx_after_chunk is ctx_after_parse

    ctx_after_ingest = await pipeline.ingest_documents(ctx_after_chunk, session=None)
    assert ctx_after_ingest.skip_embed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_runs_all_steps_when_parser_changes(monkeypatch: pytest.MonkeyPatch):
    version = IngestionVersion(collection='c', parser_fp='p', chunker_fp='c', embedding_fp='e')
    record = SimpleNamespace(parser_fp='other', chunker_fp='c', embedding_fp='e')
    plan = version.plan_for(record)

    pipeline = UploadPipeline(store=DummyStore())

    async def fake_load_cached_markdown(self, ctx):
        return None, None

    monkeypatch.setattr(UploadPipeline, '_load_cached_markdown', fake_load_cached_markdown)

    parser_instances: list = []

    class FakeParser:
        def __init__(self):
            self.parse_called = False
            parser_instances.append(self)

        async def parse(self, file: str):
            self.parse_called = True
            return [Document(page_content='parsed body', metadata={})]

        async def to_markdown(self) -> str:
            return '# Parsed'

    chunk_calls = {'called': False}

    def fake_chunker(docs):
        chunk_calls['called'] = True
        return [Document(page_content='chunked', metadata={'parser': 'LlamaParser'})]

    delete_calls = {'count': 0}
    ingest_calls: list = []

    class FakeIngestor:
        def __init__(self, collection: str):
            self.collection = collection

        async def ingest(self, session, docs, job_id):
            ingest_calls.append({'session': session, 'docs': docs, 'job_id': job_id})
            return SimpleNamespace(ingestion_id=uuid4())

    async def fake_find(*args, **kwargs):
        return None

    async def fake_fetch(*args, **kwargs):
        return []

    async def fake_delete(*args, **kwargs):
        delete_calls['count'] += 1

    async def fake_job_update(*args, **kwargs):
        return None

    monkeypatch.setattr('services.upload_steps.LlamaParser', FakeParser)
    monkeypatch.setattr('services.upload_steps.chunk_documents_by_headings', fake_chunker)
    monkeypatch.setattr('services.upload_steps.DocumentIngestor', FakeIngestor)
    monkeypatch.setattr('services.upload_steps.ingestion_repository.find', fake_find)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.fetch_documents', fake_fetch)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.delete', fake_delete)
    monkeypatch.setattr('services.upload_steps.job_repository.update', fake_job_update)

    existing_ingestion = SimpleNamespace(id=uuid4())
    ctx = _build_ctx(plan=plan, existing_ingestion=existing_ingestion)

    ctx_after_parse = await pipeline.parse_document(ctx)
    assert parser_instances and parser_instances[0].parse_called is True
    assert ctx_after_parse.run_parser is True
    assert ctx_after_parse.markdown_text == '# Parsed'

    ctx_after_chunk = await pipeline.chunk_documents(ctx_after_parse)
    assert chunk_calls['called'] is True
    assert ctx_after_chunk.docs and ctx_after_chunk.docs[0].page_content == 'chunked'

    ctx_after_ingest = await pipeline.ingest_documents(ctx_after_chunk, session='session')
    assert delete_calls['count'] == 1
    assert len(ingest_calls) == 1
    assert ctx_after_ingest.skip_embed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_runs_chunker_and_embedding_when_only_chunker_changes(monkeypatch: pytest.MonkeyPatch):
    version = IngestionVersion(collection='c', parser_fp='p', chunker_fp='c', embedding_fp='e')
    record = SimpleNamespace(parser_fp='p', chunker_fp='other', embedding_fp='e')
    plan = version.plan_for(record)

    pipeline = UploadPipeline(store=DummyStore())

    async def fake_load_cached_markdown(self, ctx):
        return '# cached markdown', 'cached.md'

    monkeypatch.setattr(UploadPipeline, '_load_cached_markdown', fake_load_cached_markdown)

    class FailParser:
        def __init__(self, *args, **kwargs):
            raise AssertionError('Parser should be skipped when unchanged')

    chunk_calls = {'called': False}

    def fake_chunker(docs):
        chunk_calls['called'] = True
        return [Document(page_content='chunked', metadata={'parser': 'LlamaParser'})]

    ingest_calls: list = []

    class FakeIngestor:
        def __init__(self, collection: str):
            self.collection = collection

        async def ingest(self, session, docs, job_id):
            ingest_calls.append({'docs': docs, 'job_id': job_id})
            return SimpleNamespace(ingestion_id=uuid4())

    async def fake_find(*args, **kwargs):
        return None

    async def fake_fetch(*args, **kwargs):
        return []

    async def fake_delete(*args, **kwargs):
        return None

    async def fake_job_update(*args, **kwargs):
        return None

    monkeypatch.setattr('services.upload_steps.LlamaParser', FailParser)
    monkeypatch.setattr('services.upload_steps.chunk_documents_by_headings', fake_chunker)
    monkeypatch.setattr('services.upload_steps.DocumentIngestor', FakeIngestor)
    monkeypatch.setattr('services.upload_steps.ingestion_repository.find', fake_find)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.fetch_documents', fake_fetch)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.delete', fake_delete)
    monkeypatch.setattr('services.upload_steps.job_repository.update', fake_job_update)

    ctx = _build_ctx(plan=plan)

    ctx_after_parse = await pipeline.parse_document(ctx)
    assert ctx_after_parse.run_parser is False
    assert ctx_after_parse.docs, 'Cached markdown should be converted to docs'

    ctx_after_chunk = await pipeline.chunk_documents(ctx_after_parse)
    assert chunk_calls['called'] is True
    assert ctx_after_chunk.docs and ctx_after_chunk.docs[0].page_content == 'chunked'

    ctx_after_ingest = await pipeline.ingest_documents(ctx_after_chunk, session=None)
    assert ingest_calls, 'Embedding should run when chunker changes'
    assert ctx_after_ingest.skip_embed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_runs_only_embedding_when_embedding_changes(monkeypatch: pytest.MonkeyPatch):
    version = IngestionVersion(collection='c', parser_fp='p', chunker_fp='c', embedding_fp='e')
    record = SimpleNamespace(parser_fp='p', chunker_fp='c', embedding_fp='other')
    plan = version.plan_for(record)

    pipeline = UploadPipeline(store=DummyStore())

    async def fake_load_cached_markdown(self, ctx):
        return '# cached markdown', 'cached.md'

    monkeypatch.setattr(UploadPipeline, '_load_cached_markdown', fake_load_cached_markdown)

    class FailParser:
        def __init__(self, *args, **kwargs):
            raise AssertionError('Parser should be skipped when unchanged')

    def fail_chunker(*args, **kwargs):
        raise AssertionError('Chunker should not run when unchanged')

    ingest_calls: list = []

    class FakeIngestor:
        def __init__(self, collection: str):
            self.collection = collection

        async def ingest(self, session, docs, job_id):
            ingest_calls.append({'docs': docs, 'job_id': job_id})
            return SimpleNamespace(ingestion_id=uuid4())

    async def fake_find(*args, **kwargs):
        return None

    async def fake_fetch(*args, **kwargs):
        return []

    async def fake_delete(*args, **kwargs):
        return None

    async def fake_job_update(*args, **kwargs):
        return None

    monkeypatch.setattr('services.upload_steps.LlamaParser', FailParser)
    monkeypatch.setattr('services.upload_steps.chunk_documents_by_headings', fail_chunker)
    monkeypatch.setattr('services.upload_steps.DocumentIngestor', FakeIngestor)
    monkeypatch.setattr('services.upload_steps.ingestion_repository.find', fake_find)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.fetch_documents', fake_fetch)
    monkeypatch.setattr('services.upload_steps.embeddings_repository.delete', fake_delete)
    monkeypatch.setattr('services.upload_steps.job_repository.update', fake_job_update)

    initial_doc = Document(page_content='ready', metadata={})
    ctx = _build_ctx(plan=plan, docs=[initial_doc])

    ctx_after_parse = await pipeline.parse_document(ctx)
    assert ctx_after_parse.docs and ctx_after_parse.docs[0].page_content.startswith('# cached')

    ctx_after_chunk = await pipeline.chunk_documents(ctx_after_parse)
    assert ctx_after_chunk is ctx_after_parse

    ctx_after_ingest = await pipeline.ingest_documents(ctx_after_chunk, session=None)
    assert ingest_calls, 'Embedding should run when embedding changes'
    assert ctx_after_ingest.skip_embed is False
