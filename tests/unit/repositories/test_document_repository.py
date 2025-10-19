from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.sql.elements import BinaryExpression

from app.repositories.document_repo import DocumentRepository
from app.repositories.models import DocumentRecord


def _has_column(clause: object, column) -> bool:
    return isinstance(clause, BinaryExpression) and clause.left.compare(column)


@pytest.mark.anyio
async def test_get_many_applies_filters_and_pagination(monkeypatch):
    context = MagicMock(tenant_id=uuid4(), user_id=uuid4())
    monkeypatch.setattr(
        'app.repositories.document_repo.AccessContext.from_session',
        MagicMock(return_value=context),
    )

    session = AsyncMock()
    rows = [object(), object(), object()]
    scalar = MagicMock()
    scalar.all.return_value = rows
    session.exec.return_value = scalar

    repo = DocumentRepository()
    result = await repo.get_many(
        session,
        filters={
            'limit': 2,
            'offset': 0,
            'collection': 'default',
            'query': 'report',
        },
    )

    session.exec.assert_awaited_once()
    stmt = session.exec.await_args.args[0]
    where_clauses = list(stmt._where_criteria)

    assert any(_has_column(clause, DocumentRecord.tenant_id) for clause in where_clauses)
    assert any(_has_column(clause, DocumentRecord.collection) for clause in where_clauses)
    assert any(_has_column(clause, DocumentRecord.original_filename) for clause in where_clauses)

    assert result['items'] == rows[:2]
    assert result['next_page_token'] == '2'

    session.exec.reset_mock()
    scalar.all.return_value = rows[:2]
    session.exec.return_value = scalar

    result = await repo.get_many(session, filters={'limit': 2, 'offset': 2})
    assert result['items'] == rows[:2]
    assert result['next_page_token'] is None
    session.exec.assert_awaited_once()
