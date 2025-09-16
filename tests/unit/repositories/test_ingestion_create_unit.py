from __future__ import annotations

from uuid import uuid4

import pytest

from app.repositories.schemas import IngestionCreate
from app.vector.models import IngestorSettings


@pytest.mark.unit
async def test_from_settings_populates_fields(digest_random):
    document_id = uuid4()
    job_id = uuid4()
    collection = 'finance'

    ic = IngestionCreate.create(document_id=document_id, collection=collection, job_id=job_id, digest=digest_random)

    defaults = IngestorSettings()
    assert ic.document_id == document_id
    assert ic.job_id == job_id
    assert ic.collection == collection

    # Settings-mirrored fields
    assert ic.chunker_model == defaults.chunker_model
    assert ic.chunker_version == defaults.chunker_version
    assert ic.chunker_params == defaults.chunker_params
    assert ic.embed_model == defaults.embed_model
    assert ic.embed_model_version == defaults.embed_model_version
    assert ic.embed_dim == defaults.embed_dim

    # Should be defaulted at construction time
    assert isinstance(ic.num_chunks, int)
    assert ic.num_chunks == 0


@pytest.mark.unit
async def test_fingerprint_independence_and_collection_dependence(digest_random):
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
