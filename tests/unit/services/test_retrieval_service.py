from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.documents import Document
from tenauth.schemas import AccessContext

from schemas.search import ChunkSearchRequest
from services.retrieval_service import RetrievalService


async def test_search_builds_filters_and_filters_scores(monkeypatch):
    vectorstore = AsyncMock()
    vectorstore.asimilarity_search_with_score.return_value = [
        (Document(page_content='kept', metadata={'chunk_id': 1, 'page': 2}), 0.9),
        (Document(page_content='dropped', metadata={'chunk_id': 3}), 0.1),
    ]

    monkeypatch.setattr('services.retrieval_service.get_vectorstore', lambda **kwargs: vectorstore)

    payload = ChunkSearchRequest(
        collection='default',
        query='profit',
        digest='vI7EHYpQg6bnz2PsLviZVeneXbMs9iqDQyOgUjIhClc=',
        limit=5,
        metadata_filter={'source': {'$eq': 'file.pdf'}},
        exclude_chunk_ids=[1],
        score_threshold=0.5,
    )
    access = AccessContext(tenant_id=uuid4(), user_id=uuid4())

    service = RetrievalService()
    response = await service.search(payload=payload, access=access)

    vectorstore.asimilarity_search_with_score.assert_awaited_once()
    kwargs = vectorstore.asimilarity_search_with_score.await_args.kwargs
    assert kwargs['k'] == 5
    assert kwargs['filter'] == {
        '$and': [
            {'digest': {'$eq': payload.digest}},
            {'source': {'$eq': 'file.pdf'}},
            {'chunk_id': {'$nin': [1]}},
        ]
    }

    assert len(response.results) == 1
    match = response.results[0]
    assert match.chunk_id == '1'
    assert match.metadata['page'] == 2
    assert response.collection_exists is True
