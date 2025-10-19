from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.repositories.document_repo import DocumentRepository
from app.schemas.documents import DocumentListFilters
from app.services.document_service import DocumentService
from tests.support.profiles import TestProcessingProfile


@pytest.mark.anyio
async def test_list_documents_resolves_profile_and_pagination():
    repo = AsyncMock(spec=DocumentRepository)
    repo.get_many.return_value = {'items': [], 'next_page_token': '5'}
    service = DocumentService(repo=repo)
    filters = DocumentListFilters(
        profileName=TestProcessingProfile.name,
        limit=5,
        nextPageToken='10',
    )

    response = await service.list_documents(AsyncMock(), filters=filters)

    repo.get_many.assert_awaited_once()
    repo_filters = repo.get_many.await_args.kwargs['filters']
    assert repo_filters['collection'] == TestProcessingProfile.collection
    assert repo_filters['limit'] == 5
    assert repo_filters['offset'] == 10
    assert response.next_page_token == '5'
    assert response.items == []


@pytest.mark.anyio
async def test_list_documents_handles_unknown_profile():
    repo = AsyncMock(spec=DocumentRepository)
    repo.get_many.return_value = {'items': [], 'next_page_token': None}
    service = DocumentService(repo=repo)
    filters = DocumentListFilters(profileName='does-not-exist')

    await service.list_documents(AsyncMock(), filters=filters)

    repo.get_many.assert_awaited_once()
    repo_filters = repo.get_many.await_args.kwargs['filters']
    assert 'collection' not in repo_filters
