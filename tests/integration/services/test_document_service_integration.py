from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from api.file import TemporaryUploadFile
from repositories import (
    document_repository,
    embeddings_repository,
    ingestion_repository,
    job_repository,
)
from repositories.exceptions import RecordNotFoundError
from repositories.schemas import DocumentCreate, IngestionCreate, JobCreate
from schemas.upload import JobStatus
from services.factory import get_document_service
from store.local_store import LocalFileStore
from vector.factory import get_vectorstore

pytestmark = pytest.mark.integration


class _FakeEmbeddings(Embeddings):
    def __init__(self) -> None:
        self.dim = 1536

    def embed_documents(self, texts):
        return [[0.0] * self.dim for _ in texts]

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    def embed_query(self, text):
        return [0.0] * self.dim

    async def aembed_query(self, text):
        return self.embed_query(text)


async def test_document_service_delete_cleans_references(auth_session, digest_random, tmp_path):
    service = get_document_service()
    document_create = DocumentCreate(
        collection='default',
        digest=digest_random,
        original_filename='cleanup.pdf',
        content_type='application/pdf',
        size_bytes=123,
        meta={'purpose': 'delete'},
    )
    document = await document_repository.create(auth_session, data=document_create)

    store = LocalFileStore(document.collection)
    original_path = tmp_path / 'cleanup.pdf'
    original_path.write_bytes(b'%PDF-1.4\n%%EOF')
    temp_file = TemporaryUploadFile(path=original_path, filename='cleanup.pdf', content_type='application/pdf')
    try:
        await store.save_original(
            temp_file,
            document_id=document.id,
            digest=document.digest,
            tenant_id=document.tenant_id,
        )
    finally:
        temp_file.close()

    await store.save_markdown(
        '# cleanup',
        document_id=document.id,
        digest=document.digest,
        tenant_id=document.tenant_id,
    )

    job = await job_repository.create(
        auth_session,
        job=JobCreate(
            document_id=document.id,
            status=JobStatus.PROCESSING,
            percent=0,
            step='init',
        ),
    )

    ingestion = await ingestion_repository.create(
        auth_session,
        data=IngestionCreate.create(
            collection=document.collection,
            document_id=document.id,
            digest=document.digest,
            job_id=job.id,
        ),
    )

    vectorstore = get_vectorstore(
        collection=document.collection,
        tenant_id=document.tenant_id,
        embeddings=_FakeEmbeddings(),
    )
    await vectorstore.aadd_documents(
        [
            Document(
                page_content='content',
                metadata={'digest': document.digest, 'source': document.original_filename},
            )
        ]
    )

    assert await embeddings_repository.exists(
        auth_session,
        collection=document.collection,
        digest=document.digest,
    )

    info_before = await store.info(
        document_id=document.id,
        digest=document.digest,
        tenant_id=document.tenant_id,
    )
    assert info_before.files

    await service.delete(auth_session, document_id=document.id)

    with pytest.raises(RecordNotFoundError):
        await document_repository.get(auth_session, document_id=document.id)

    with pytest.raises(RecordNotFoundError):
        await job_repository.get(auth_session, job_id=job.id)

    with pytest.raises(RecordNotFoundError):
        await ingestion_repository.get(auth_session, ingestion_id=ingestion.id)

    assert not await embeddings_repository.exists(
        auth_session,
        collection=document.collection,
        digest=document.digest,
    )

    info_after = await store.info(
        document_id=document.id,
        digest=document.digest,
        tenant_id=document.tenant_id,
    )
    assert info_after.files == []

    prefix_path = Path(store._prefix(tenant_id=document.tenant_id, digest=document.digest))
    assert not prefix_path.exists()
