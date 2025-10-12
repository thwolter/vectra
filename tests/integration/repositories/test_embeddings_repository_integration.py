import uuid

import pytest
from langchain_core.documents import Document

from app.repositories import EmbeddingsRepository
from app.schemas.enums import CollectionEnum
from app.vector.factory import get_vectorstore
from app.vector.ingestor import IngestorSettings


@pytest.mark.needs_postgres
@pytest.mark.needs_openai
async def test_check_documents_exists_scoped_by_collection(
    session,
):
    digest = uuid.uuid4().hex[:10]

    tenant_id = session.info['tenant_id']
    vs_default = get_vectorstore(
        collection=CollectionEnum.DEFAULT.value, tenant_id=tenant_id, config=IngestorSettings()
    )
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
