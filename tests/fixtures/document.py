from typing import AsyncGenerator

import pytest

from app.repositories import DocumentRepository
from app.repositories.models import DocumentRecord
from app.repositories.schemas import DocumentCreate


@pytest.fixture
async def document_created(session, digest_random) -> AsyncGenerator[DocumentRecord, None]:
    document_create = DocumentCreate(
        collection='default',
        digest=digest_random,
        original_filename='test_original_filename.pdf',
        content_type='application/pdf',
        size_bytes=1024,
        meta={'company': 'ACME Inc.'},
    )
    record = await DocumentRepository.create(session, data=document_create)
    yield record
    await session.delete(record)
