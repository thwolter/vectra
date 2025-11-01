import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from repositories import embeddings_repository
from vector.factory import get_vectorstore


@pytest.mark.integration
async def test_get_document_by_id(auth_client, document_created):
    res = await auth_client.get(f'/api/v1/documents/{document_created.id}')
    assert res.status_code == 200, res.text
    assert res.json()['id'] == str(document_created.id)


@pytest.mark.integration
async def test_update_document_filename_updates_embeddings(auth_client, auth_session, document_created):
    class _FakeEmbeddings(Embeddings):
        def __init__(self, *_, **__):
            self.dim = 1536

        def embed_documents(self, texts):
            return [[float(idx)] * self.dim for idx, _ in enumerate(texts)]

        async def aembed_documents(self, texts):
            return self.embed_documents(texts)

        def embed_query(self, text):
            return [0.0] * self.dim

        async def aembed_query(self, text):
            return self.embed_query(text)

    vectorstore = get_vectorstore(
        collection=document_created.collection,
        tenant_id=document_created.tenant_id,
        embeddings=_FakeEmbeddings(),
    )
    await vectorstore.aadd_documents(
        [
            Document(
                page_content='stub',
                metadata={'digest': document_created.digest, 'source': document_created.original_filename},
            )
        ]
    )

    new_filename = 'updated-name.pdf'
    response = await auth_client.patch(
        f'/api/v1/documents/{document_created.id}/filename',
        json={'original_filename': new_filename},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['id'] == str(document_created.id)
    assert payload['original_filename'] == new_filename

    await auth_session.refresh(document_created)
    assert document_created.original_filename == new_filename

    docs = await embeddings_repository.fetch_documents(
        auth_session,
        collection=document_created.collection,
        digest=document_created.digest,
    )
    assert docs, 'expected embeddings to exist for digest'
    assert all(doc.metadata.get('source') == new_filename for doc in docs)
