from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from repositories.document_repo import DocumentRepository
from repositories.embeddings_repo import EmbeddingsRepository
from schemas.documents import DocumentListFilters
from services.document_service import DocumentService


async def test_list_documents_resolves_profile_and_pagination():
    repo = AsyncMock(spec=DocumentRepository)
    repo.get_many.return_value = {'items': [], 'next_page_token': '5'}
    service = DocumentService(repo=repo)
    filters = DocumentListFilters(
        limit=5,
        nextPageToken='10',
    )

    response = await service.list_documents(AsyncMock(), filters=filters)

    repo.get_many.assert_awaited_once()
    repo_filters = repo.get_many.await_args.kwargs['filters']
    assert repo_filters['limit'] == 5
    assert repo_filters['offset'] == 10
    assert response.next_page_token == '5'
    assert response.items == []


async def test_update_original_filename_updates_repositories():
    repo = AsyncMock(spec=DocumentRepository)
    embeddings_repo = AsyncMock(spec=EmbeddingsRepository)
    service = DocumentService(repo=repo, embeddings_repo=embeddings_repo)
    session = AsyncMock()

    document_id = uuid4()
    now = datetime.now(timezone.utc)
    record = SimpleNamespace(
        id=document_id,
        digest='6ZyNzbDIcgh73BVOFU5y/EJYEeLFVtJB3Xya1djn4Cs=',
        collection='default',
        original_filename='renamed.pdf',
        content_type='application/pdf',
        size_bytes=123,
        original_uri=None,
        markdown_uri=None,
        meta={'company': 'ACME'},
        created_at=now,
        created_by=uuid4(),
        updated_at=now,
    )
    repo.update.return_value = record

    response = await service.update_original_filename(
        session,
        document_id=document_id,
        original_filename='renamed.pdf',
    )

    repo.update.assert_awaited_once()
    update_kwargs = repo.update.await_args.kwargs
    assert update_kwargs['document'].id == document_id
    assert update_kwargs['document'].original_filename == 'renamed.pdf'

    embeddings_repo.update_source.assert_awaited_once_with(
        session,
        collection='default',
        digest='6ZyNzbDIcgh73BVOFU5y/EJYEeLFVtJB3Xya1djn4Cs=',
        source='renamed.pdf',
    )

    assert response.original_filename == 'renamed.pdf'
