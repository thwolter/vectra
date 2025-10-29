from __future__ import annotations

from unittest.mock import AsyncMock

from repositories.document_repo import DocumentRepository
from schemas.documents import DocumentListFilters
from services.document_service import DocumentService
from tests.support.profiles import TestProcessingProfile  # type: ignore[missing-import]


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
