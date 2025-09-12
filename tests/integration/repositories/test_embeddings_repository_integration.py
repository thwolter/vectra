import uuid

import pytest

from langchain_core.documents import Document

from app.repositories.embeddings import Embeddings
from app.schemas.enums import CollectionEnum
from app.vector.factory import get_vectorstore


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_document_metadata_by_digest_merges_across_all_chunks(session):
    vs = get_vectorstore(CollectionEnum.FINANCIAL.value)
    digest = uuid.uuid4().hex[:10]

    docs = [
        Document(page_content='Chunk 0', metadata={'digest': digest, 'existing': 'v0'}),
        Document(page_content='Chunk 1', metadata={'digest': digest, 'existing': 'v1'}),
    ]
    vs.add_documents(documents=docs)

    updates = {'company': 'Acme', 'year': 2024}
    await Embeddings.update_metadata(
        session,
        digest=digest,
        metadata=updates,
        collection=CollectionEnum.FINANCIAL.value,
    )

    metas = await Embeddings.get_metadata(
        session, digest=digest, collection=CollectionEnum.FINANCIAL.value
    )
    assert len(metas) == 2
    for m in metas:
        assert m['digest'] == digest
        assert m['company'] == 'Acme'
        assert m['year'] == 2024
        assert 'existing' in m  # preserved existing keys

    await Embeddings.delete(session, digest=digest)


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_metadata_keeps_existing_metadata_when_replace_false(
    session,
):
    vs = get_vectorstore(CollectionEnum.FINANCIAL.value)
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
    await Embeddings.update_metadata(
        session,
        digest=digest,
        metadata={'existing': 'v2'},
        collection=CollectionEnum.FINANCIAL.value,
    )
    metas = await Embeddings.get_metadata(
        session, digest=digest, collection=CollectionEnum.FINANCIAL.value
    )
    assert len(metas) == 2
    for m in metas:
        assert m['digest'] == digest
        assert m['existing'] == 'v2'
        assert m['keep'] == 'keep_this'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_metadata_replaces_metadata_when_replace_true(
    session,
):
    vs = get_vectorstore(CollectionEnum.FINANCIAL.value)
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
    await Embeddings.update_metadata(
        session,
        digest=digest,
        metadata={'existing': 'v2'},
        collection=CollectionEnum.FINANCIAL.value,
        replace=True,
    )
    metas = await Embeddings.get_metadata(
        session, digest=digest, collection=CollectionEnum.FINANCIAL.value
    )
    assert len(metas) == 2
    for m in metas:
        assert m['digest'] == digest
        assert m['existing'] == 'v2'
        assert 'keep' not in m


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_check_documents_exists_scoped_by_collection(
    session,
):
    digest = uuid.uuid4().hex[:10]

    vs_default = get_vectorstore(CollectionEnum.DEFAULT.value)
    vs_default.add_documents(
        documents=[
            Document(
                page_content='Hello',
                metadata={'digest': digest, 'source': 'key.pdf'},
            )
        ]
    )

    assert (
        await Embeddings.exists_by_digest(
            session, digest=digest, collection=CollectionEnum.DEFAULT.value
        )
        is True
    )
    assert (
        await Embeddings.exists_by_digest(
            session, digest=digest, collection=CollectionEnum.FINANCIAL.value
        )
        is False
    )
    assert (
        await Embeddings.exists_by_digest(
            session, digest='123', collection=CollectionEnum.FINANCIAL.value
        )
        is False
    )

    assert (
        await Embeddings.exists_by_source(
            session, source='key.pdf', collection=CollectionEnum.DEFAULT.value
        )
        is True
    )
    assert (
        await Embeddings.exists_by_source(
            session, source='key.pdf', collection=CollectionEnum.FINANCIAL.value
        )
        is False
    )

    await Embeddings.delete(session, digest=digest)


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_document_metadata_noop_on_empty_updates(
    session,
):
    vs = get_vectorstore(CollectionEnum.DEFAULT.value)
    digest = uuid.uuid4().hex[:10]

    # Insert one chunk via vector
    vs.add_documents(
        documents=[Document(page_content='X', metadata={'digest': digest})]
    )

    # Call with empty updates -> no exception, metadata unchanged
    await Embeddings.update_metadata(
        session, digest=digest, metadata={}, collection=CollectionEnum.DEFAULT.value
    )
    metas = await Embeddings.get_metadata(
        session, digest=digest, collection=CollectionEnum.DEFAULT.value
    )
    assert len(metas) == 1
    assert metas[0]['digest'] == digest

    await Embeddings.delete(session, digest=digest)
