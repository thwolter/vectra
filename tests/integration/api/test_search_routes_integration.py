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
    finally:
        await embeddings_repository.delete(auth_session, digest=digest)
