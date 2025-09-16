import uuid

import pytest
from langchain_core.documents import Document

from app.repositories import EmbeddingsRepository
from app.schemas.enums import CollectionEnum
from app.vector.factory import get_vectorstore


@pytest.mark.needs_postgres
@pytest.mark.needs_openai
async def test_update_document_metadata_by_digest_merges_across_all_chunks(session):
    tenant_id = session.info['tenant_id']
    vs = get_vectorstore(CollectionEnum.FINANCIAL.value, tenant_id=tenant_id)
    digest = uuid.uuid4().hex[:10]

    docs = [
        Document(page_content='Chunk 0', metadata={'digest': digest, 'existing': 'v0'}),
        Document(page_content='Chunk 1', metadata={'digest': digest, 'existing': 'v1'}),
    ]
    vs.add_documents(documents=docs)

    updates = {'company': 'Acme', 'year': 2024}
    await EmbeddingsRepository.update_metadata(
        session,
        digest=digest,
        metadata=updates,
        collection=CollectionEnum.FINANCIAL.value,
    )

    metas = await EmbeddingsRepository.get_metadata(session, digest=digest, collection=CollectionEnum.FINANCIAL.value)
    assert len(metas) == 2
    for m in metas:
        assert m['digest'] == digest
        assert m['company'] == 'Acme'
        assert m['year'] == 2024
        assert 'existing' in m  # preserved existing keys

    await EmbeddingsRepository.delete(session, digest=digest)


@pytest.mark.needs_postgres
@pytest.mark.needs_openai
async def test_update_metadata_keeps_existing_metadata_when_replace_false(
    session,
):
    tenant_id = session.info['tenant_id']
    vs = get_vectorstore(collection=CollectionEnum.FINANCIAL.value, tenant_id=tenant_id)
    digest = uuid.uuid4().hex[:10]
    docs = [
        Document(
            page_content='Chunk 0',
            metadata={'digest': digest, 'existing': 'v0', 'keep': 'keep_this'},
        ),
        Document(
            page_content='Chunk 1',
            metadata={'digest': digest, 'existing': 'v1', 'keep': 'keep_this'},
        ),
    ]
    vs.add_documents(documents=docs)
    await EmbeddingsRepository.update_metadata(
        session,
        digest=digest,
        metadata={'existing': 'v2'},
        collection=CollectionEnum.FINANCIAL.value,
    )
    metas = await EmbeddingsRepository.get_metadata(session, digest=digest, collection=CollectionEnum.FINANCIAL.value)
    assert len(metas) == 2
    for m in metas:
        assert m['digest'] == digest
        assert m['existing'] == 'v2'
        assert m['keep'] == 'keep_this'


@pytest.mark.needs_postgres
@pytest.mark.needs_openai
async def test_update_metadata_replaces_metadata_when_replace_true(
    session,
):
    tenant_id = session.info['tenant_id']
    vs = get_vectorstore(collection=CollectionEnum.FINANCIAL.value, tenant_id=tenant_id)
    digest = uuid.uuid4().hex[:10]
    docs = [
        Document(
            page_content='Chunk 0',
            metadata={'digest': digest, 'existing': 'v0', 'keep': 'keep_this'},
        ),
        Document(
            page_content='Chunk 1',
            metadata={'digest': digest, 'existing': 'v1', 'keep': 'keep_this'},
        ),
    ]
    vs.add_documents(documents=docs)
    # Replace metadata entirely (except digest must be preserved by Embeddings implementation)
    await EmbeddingsRepository.update_metadata(
        session,
        digest=digest,
        metadata={'existing': 'v2'},
        collection=CollectionEnum.FINANCIAL.value,
        replace=True,
    )
    metas = await EmbeddingsRepository.get_metadata(session, digest=digest, collection=CollectionEnum.FINANCIAL.value)
    assert len(metas) == 2
    for m in metas:
        assert m['digest'] == digest
        assert m['existing'] == 'v2'
        assert 'keep' not in m


@pytest.mark.needs_postgres
@pytest.mark.needs_openai
async def test_check_documents_exists_scoped_by_collection(
    session,
):
    digest = uuid.uuid4().hex[:10]

    tenant_id = session.info['tenant_id']
    vs_default = get_vectorstore(collection=CollectionEnum.DEFAULT.value, tenant_id=tenant_id)
    vs_default.add_documents(
        documents=[
            Document(
                page_content='Hello',
                metadata={'digest': digest, 'source': 'key.pdf'},
            )
        ]
    )

    assert await EmbeddingsRepository.exists(session, digest=digest, collection=CollectionEnum.DEFAULT.value) is True
    assert await EmbeddingsRepository.exists(session, digest=digest, collection=CollectionEnum.FINANCIAL.value) is False
    assert await EmbeddingsRepository.exists(session, digest='123', collection=CollectionEnum.FINANCIAL.value) is False

    assert await EmbeddingsRepository.exists(session, source='key.pdf', collection=CollectionEnum.DEFAULT.value) is True
    assert (
        await EmbeddingsRepository.exists(session, source='key.pdf', collection=CollectionEnum.FINANCIAL.value) is False
    )

    await EmbeddingsRepository.delete(session, digest=digest)


@pytest.mark.needs_postgres
@pytest.mark.needs_openai
async def test_update_document_metadata_noop_on_empty_updates(
    session,
):
    tenant_id = session.info['tenant_id']
    vs = get_vectorstore(collection=CollectionEnum.DEFAULT.value, tenant_id=tenant_id)
    digest = uuid.uuid4().hex[:10]

    # Insert one chunk via vector
    vs.add_documents(documents=[Document(page_content='X', metadata={'digest': digest})])

    # Call with empty updates -> no exception, metadata unchanged
    await EmbeddingsRepository.update_metadata(
        session, digest=digest, metadata={}, collection=CollectionEnum.DEFAULT.value
    )
    metas = await EmbeddingsRepository.get_metadata(session, digest=digest, collection=CollectionEnum.DEFAULT.value)
    assert len(metas) == 1
    assert metas[0]['digest'] == digest

    await EmbeddingsRepository.delete(session, digest=digest)
