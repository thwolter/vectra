from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from repositories import embeddings_repository
from vector.factory import get_vectorstore


class _FakeEmbeddings(Embeddings):
    def __init__(self, *, dim: int = 1536) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        base = float(sum(ord(char) for char in text) % 10)
        return [base + idx for idx in range(self.dim)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


async def test_search_chunks_filters_results(auth_client, auth_session, digest_from):
    digest = digest_from('finance-doc')
    other_digest = digest_from('other-doc')
    tenant_id = auth_session.info['tenant_id']
    vectorstore = get_vectorstore(collection='default', tenant_id=tenant_id, embeddings=_FakeEmbeddings())

    docs = [
        Document(
            page_content='Revenue grew 20% year over year for the finance division.',
            metadata={'chunk_id': 1, 'digest': digest, 'topic': 'finance'},
        ),
        Document(
            page_content='Cost controls improved margins across the finance organization.',
            metadata={'chunk_id': 2, 'digest': digest, 'topic': 'finance'},
        ),
        Document(
            page_content='Unrelated material for a different digest.',
            metadata={'chunk_id': 3, 'digest': other_digest, 'topic': 'other'},
        ),
    ]

    await vectorstore.aadd_documents(docs)

    try:
        response = await auth_client.post(
            '/api/v1/search/chunks',
            json={
                'collection': 'default',
                'query': 'finance revenue growth',
                'digest': digest,
                'metadata_filter': {'topic': {'$eq': 'finance'}},
                'exclude_chunk_ids': [2],
                'limit': 5,
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert len(payload['results']) == 1
        assert payload['collection_exists'] is True

        match = payload['results'][0]
        assert match['chunk_id'] == '1'
        assert match['metadata']['topic'] == 'finance'
        assert match['metadata']['digest'] == digest
        assert match['score'] >= 0
    finally:
        await embeddings_repository.delete(auth_session, digest=digest)
        await embeddings_repository.delete(auth_session, digest=other_digest)


async def test_search_chunks_minimal_payload(auth_client, auth_session, digest_from):
    digest = digest_from('minimal-doc')
    tenant_id = auth_session.info['tenant_id']
    vectorstore = get_vectorstore(collection='default', tenant_id=tenant_id, embeddings=_FakeEmbeddings())

    docs = [
        Document(page_content='First note about the product launch.', metadata={'chunk_id': 1, 'digest': digest}),
        Document(page_content='Second note touching on the same product.', metadata={'chunk_id': 2, 'digest': digest}),
    ]

    await vectorstore.aadd_documents(docs)

    try:
        response = await auth_client.post('/api/v1/search/chunks', json={'query': 'product note', 'digest': digest})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert len(payload['results']) == 2
        assert {result['chunk_id'] for result in payload['results']} == {'1', '2'}
        assert payload['collection_exists'] is True
    finally:
        await embeddings_repository.delete(auth_session, digest=digest)


async def test_search_chunks_missing_collection(auth_client, auth_session, digest_from):
    missing_collection = 'missing-collection'
    digest = digest_from(missing_collection)

    exists_before = await embeddings_repository.collection_exists(auth_session, collection=missing_collection)
    assert exists_before is False

    response = await auth_client.post(
        '/api/v1/search/chunks',
        json={'collection': missing_collection, 'query': 'anything', 'digest': digest},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['results'] == []
    assert payload['collection_exists'] is False

    exists_after = await embeddings_repository.collection_exists(auth_session, collection=missing_collection)
    assert exists_after is False


async def test_document_availability_by_document_id(auth_client, document_created):
    response = await auth_client.post(
        '/api/v1/search/document-availability',
        json={
            'document_id': str(document_created.id),
            'collection': document_created.collection,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['id'] == str(document_created.id)
    assert payload['digest'] == document_created.digest


async def test_document_availability_by_digest(auth_client, document_created):
    response = await auth_client.post(
        '/api/v1/search/document-availability',
        json={
            'digest': document_created.digest,
            'collection': document_created.collection,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['id'] == str(document_created.id)


async def test_document_availability_collection_mismatch(auth_client, document_created):
    response = await auth_client.post(
        '/api/v1/search/document-availability',
        json={
            'document_id': str(document_created.id),
            'collection': 'other-collection',
        },
    )

    assert response.status_code == 400, response.text
    assert 'does not belong to collection' in response.json()['detail']


async def test_document_availability_digest_mismatch(auth_client, document_created, digest_from):
    mismatch_digest = digest_from('availability-mismatch')
    response = await auth_client.post(
        '/api/v1/search/document-availability',
        json={
            'document_id': str(document_created.id),
            'collection': document_created.collection,
            'digest': mismatch_digest,
        },
    )

    assert response.status_code == 400, response.text
    assert 'does not match document' in response.json()['detail']


async def test_document_availability_missing(auth_client, digest_from):
    response = await auth_client.post(
        '/api/v1/search/document-availability',
        json={'digest': digest_from('missing-doc'), 'collection': 'default'},
    )

    assert response.status_code == 404, response.text
    assert response.json()['detail'] == 'Document not found'
