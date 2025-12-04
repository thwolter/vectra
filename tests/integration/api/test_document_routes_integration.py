from unittest.mock import AsyncMock
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from main import app as main_app
from repositories import embeddings_repository
from services.document_service import DocumentService
from services.factory import get_document_service as _get_document_service_dep
from vector.factory import get_vectorstore


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


async def test_get_document_by_id(auth_client, document_created):
    res = await auth_client.get(f'/api/v1/documents/{document_created.id}')
    assert res.status_code == 200, res.text
    assert res.json()['id'] == str(document_created.id)


async def test_update_document_filename_updates_embeddings(auth_client, auth_session, document_created):
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
        json={'filename': new_filename},
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


async def test_delete_document_route_delegates_to_service(auth_client):
    document_id = uuid4()
    service = AsyncMock(spec=DocumentService)

    async def _override_service():
        return service

    main_app.dependency_overrides[_get_document_service_dep] = _override_service
    try:
        response = await auth_client.delete(f'/api/v1/documents/{document_id}')
    finally:
        main_app.dependency_overrides.pop(_get_document_service_dep, None)

    assert response.status_code == 204, response.text
    service.delete.assert_awaited_once()
    delete_args, delete_kwargs = service.delete.await_args
    assert delete_kwargs['document_id'] == document_id
    assert delete_args and delete_args[0] is not None
