import uuid

import pytest

from fastapi import UploadFile
from langchain_core.documents import Document

from app.api.file import TemporaryUploadFile
from app.parsers.protocols import ParserProtocol
from app.parsers.schemas import ParseResult
from app.repositories.ingestion_repository import Ingestion
from app.schemas.jobs import JobCtx
from app.services.upload_steps import UploadPipeline
from app.schemas.enums import CollectionEnum
from app.schemas.upload import UploadHints
from app.metadata.schemas import NoopHints, FinanceReportHints
from app.store.protocols import StoreProtocol
from unittest.mock import create_autospec, AsyncMock
from app.store.schemas import ArtifactInfo
from app.vector.protocols import IngestorProtocol


async def _make_ctx(
    file: UploadFile,
    collection: CollectionEnum | None = None,
    hints: UploadHints | None = None,
    docs: list[Document] | None = None,
    markdown_text: str | None = None,
) -> JobCtx:
    if not docs:
        docs = []
    tmp_file = TemporaryUploadFile.from_upload(file)
    digest = await tmp_file.sha256_b64()
    if not collection:
        collection = CollectionEnum.DEFAULT
    if not hints:
        hints = NoopHints()
    return JobCtx(
        job_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        collection=collection,
        file=tmp_file,
        hints=hints or NoopHints(),
        digest=digest,
        docs=docs,
        markdown_text=markdown_text,
    )


def test_trough_error_when_not_initialised():
    pipeline = UploadPipeline()
    with pytest.raises(ValueError):
        print(pipeline.ctx)


@pytest.mark.asyncio
async def test_store_original_sets_original_key_and_calls_store(
    tiny_pdf_upload: UploadFile,
):
    ctx = await _make_ctx(tiny_pdf_upload)

    store = create_autospec(StoreProtocol, instance=True, spec_set=True)
    store.save_original = AsyncMock(
        return_value=ArtifactInfo(
            document_id=ctx.document_id,
            collection=ctx.collection,
            original_key='s3://bucket/key/original.pdf',
            markdown_key=None,
        )
    )
    pipeline = UploadPipeline(store=store)
    pipeline = await pipeline.init(ctx).store_original()

    assert store.save_original.await_count == 1
    assert pipeline.ctx.original_key == 's3://bucket/key/original.pdf'


@pytest.mark.asyncio
async def test_parse_document_uses_parser_provider_and_sets_docs_and_markdown(
    tiny_pdf_upload: UploadFile,
):
    ctx = await _make_ctx(tiny_pdf_upload)

    parser = create_autospec(ParserProtocol, instance=True, spec_set=True)
    parser.parse = AsyncMock(
        return_value=ParseResult(documents=[Document(page_content='Hello World')])
    )
    parser.to_markdown = AsyncMock(return_value='markdown')

    pipeline = UploadPipeline(parser=parser)
    pipeline = await pipeline.init(ctx).parse_document()

    assert parser.parse.await_count == 1
    assert parser.to_markdown.await_count == 1
    assert pipeline.ctx.docs and [Document(page_content='Hello World')]
    assert pipeline.ctx.markdown_text == 'markdown'


@pytest.mark.asyncio
async def test_ingest_documents_skips_when_version_exists(
    tiny_pdf_upload: UploadFile, fake_session_class, monkeypatch
):
    session = fake_session_class()
    ctx = await _make_ctx(tiny_pdf_upload)

    ingestor = create_autospec(IngestorProtocol, instance=True, spec_set=True)
    ingestor.ingest = AsyncMock(return_value='docid')

    FakeIngestion = create_autospec(Ingestion, instance=False, spec_set=True)
    FakeIngestion.exists = AsyncMock(return_value=True)
    # Patch the Ingestion used inside UploadPipeline module
    monkeypatch.setattr('app.services.upload_steps.Ingestion', FakeIngestion)

    pipeline = UploadPipeline(ingestor=ingestor)
    pipeline = await pipeline.init(ctx).ingest_documents(session=session)
    assert pipeline.ctx.skip_embed is True
    assert ingestor.ingest.await_count == 0


@pytest.mark.asyncio
async def test_ingest_documents_ingests_when_not_exists_and_has_docs(
    tiny_pdf_upload: UploadFile, fake_session_class, monkeypatch
):
    session = fake_session_class()
    ctx = await _make_ctx(tiny_pdf_upload, docs=[Document(page_content='Hello World')])

    ingestor = create_autospec(IngestorProtocol, instance=True, spec_set=True)
    ingestor.ingest = AsyncMock(return_value='docid')

    FakeIngestion = create_autospec(Ingestion, instance=False, spec_set=True)
    FakeIngestion.exists = AsyncMock(return_value=False)
    monkeypatch.setattr('app.services.upload_steps.Ingestion', FakeIngestion)

    pipeline = UploadPipeline(ingestor=ingestor)
    pipeline = await pipeline.init(ctx).ingest_documents(session=session)
    assert pipeline.ctx.skip_embed is False
    assert ingestor.ingest.await_count == 1


@pytest.mark.asyncio
async def test_ingest_documents_does_not_call_ingestor_when_docs_empty(
    tiny_pdf_upload: UploadFile, fake_session_class, monkeypatch
):
    session = fake_session_class()
    ctx = await _make_ctx(tiny_pdf_upload)

    ingestor = create_autospec(IngestorProtocol, instance=True, spec_set=True)
    ingestor.ingest = AsyncMock(return_value='docid')

    FakeIngestion = create_autospec(Ingestion, instance=False, spec_set=True)
    FakeIngestion.exists = AsyncMock(return_value=False)
    monkeypatch.setattr('app.services.upload_steps.Ingestion', FakeIngestion)

    pipeline = UploadPipeline(ingestor=ingestor)
    pipeline = await pipeline.init(ctx).ingest_documents(session=session)
    assert pipeline.ctx.skip_embed is False
    assert ingestor.ingest.await_count == 0


@pytest.mark.asyncio
async def test_store_markdown_saves_when_presents(tiny_pdf_upload: UploadFile):
    ctx = await _make_ctx(tiny_pdf_upload, markdown_text='markdown')

    store = create_autospec(StoreProtocol, instance=True, spec_set=True)
    store.save_markdown = AsyncMock(
        return_value=ArtifactInfo(
            document_id=ctx.document_id,
            collection=ctx.collection,
            original_key=None,
            markdown_key='s3://bucket/key/original.md',
        )
    )

    pipeline = UploadPipeline(store=store)
    pipeline = await pipeline.init(ctx).store_markdown()

    assert store.save_markdown.await_count == 1
    assert pipeline.ctx.markdown_key == 's3://bucket/key/original.md'


@pytest.mark.asyncio
async def test_store_markdown_skips_when_none(tiny_pdf_upload: UploadFile):
    ctx = await _make_ctx(tiny_pdf_upload)

    store = create_autospec(StoreProtocol, instance=True, spec_set=True)
    store.save_markdown = AsyncMock(
        return_value=ArtifactInfo(
            document_id=ctx.document_id,
            collection=ctx.collection,
            original_key=None,
            markdown_key='s3://bucket/key/original.md',
        )
    )

    pipeline = UploadPipeline(store=store)
    pipeline = await pipeline.init(ctx).store_markdown()

    assert store.save_markdown.await_count == 0
    assert pipeline.ctx.markdown_key is None


@pytest.mark.asyncio
async def test_add_docs_metadata(tiny_pdf_upload: UploadFile):
    hints = FinanceReportHints(company='Acme Inc')
    docs = [Document(page_content='Hello World')]
    ctx = await _make_ctx(tiny_pdf_upload, hints=hints, docs=docs)

    pipeline = UploadPipeline()
    pipeline = await pipeline.init(ctx).enrich_docs_metadata()
    assert pipeline.ctx.metadata == hints.model_dump(
        exclude_none=True, exclude={'strategy'}
    )
