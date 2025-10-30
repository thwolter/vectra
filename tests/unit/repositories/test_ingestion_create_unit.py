from __future__ import annotations

from uuid import uuid4

import pytest

from repositories.schemas import IngestionCreate


@pytest.mark.unit
async def test_fingerprint_independence_and_collection_dependence(digest_random):
    """Test that fingerprint is independent of volatile IDs and dependent on collection."""

    base = IngestionCreate.create(collection='c1', document_id=uuid4(), job_id=uuid4(), digest=digest_random)

    f1 = base.fingerprint()

    # Changing volatile IDs should NOT change fingerprint
    same1 = base.model_copy(update={'document_id': uuid4()})
    same2 = base.model_copy(update={'job_id': uuid4()})
    same3 = base.model_copy(update={'num_chunks': 999})

    assert same1.fingerprint() == f1
    assert same2.fingerprint() == f1
    assert same3.fingerprint() == f1

    # Changing collection SHOULD change fingerprint
    diff_collection = base.model_copy(update={'collection': 'c2'})
    assert diff_collection.fingerprint() != f1
