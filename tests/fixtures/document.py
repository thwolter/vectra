from typing import AsyncGenerator

import pytest

from repositories import document_repository
from repositories.models import DocumentRecord
from repositories.schemas import DocumentCreate


@pytest.fixture
async def document_created(auth_session, digest_random) -> AsyncGenerator[DocumentRecord, None]:
    document_create = DocumentCreate(
        collection='default',
        digest=digest_random,
        original_filename='test_original_filename.pdf',
        content_type='application/pdf',
        size_bytes=1024,
        meta={'company': 'ACME Inc.'},
    )
    record = await document_repository.create(auth_session, data=document_create)
    yield record
    await auth_session.delete(record)
