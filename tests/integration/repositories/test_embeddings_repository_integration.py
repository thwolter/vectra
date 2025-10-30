import uuid

import pytest
from langchain_core.documents import Document

from repositories import embeddings_repository
from schemas.enums import CollectionEnum
from vector.factory import get_vectorstore


@pytest.mark.needs_openai
async def test_check_documents_exists_scoped_by_collection(
    auth_session,
):
    digest = uuid.uuid4().hex[:10]

    tenant_id = auth_session.info['tenant_id']
    vs_default = get_vectorstore(collection=CollectionEnum.DEFAULT.value, tenant_id=tenant_id)
    await vs_default.aadd_documents(
        documents=[
            Document(
                page_content='Hello',
                metadata={'digest': digest, 'source': 'key.pdf'},
            )
        ]
    )

    assert (
        await embeddings_repository.exists(auth_session, digest=digest, collection=CollectionEnum.DEFAULT.value) is True
    )
    assert (
        await embeddings_repository.exists(auth_session, digest=digest, collection=CollectionEnum.FINANCIAL.value)
        is False
    )
    assert (
        await embeddings_repository.exists(auth_session, digest='123', collection=CollectionEnum.FINANCIAL.value)
        is False
    )

    assert (
        await embeddings_repository.exists(auth_session, source='key.pdf', collection=CollectionEnum.DEFAULT.value)
        is True
    )
    assert (
        await embeddings_repository.exists(auth_session, source='key.pdf', collection=CollectionEnum.FINANCIAL.value)
        is False
    )

    await embeddings_repository.delete(auth_session, digest=digest)
