from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from repositories.models import IngestionRecord
from repositories.schemas import IngestionCreate


@pytest.mark.unit
async def test_version_stability_across_transient_fields(digest_random):
    base = IngestionCreate.create(collection='c1', document_id=uuid4(), job_id=uuid4(), digest=digest_random)
    version = base.version()

    same_document = base.model_copy(update={'document_id': uuid4()})
    same_job = base.model_copy(update={'job_id': uuid4()})
    same_chunks = base.model_copy(update={'num_chunks': 999})

    assert same_document.version().parser_fp == version.parser_fp
    assert same_job.version().chunker_fp == version.chunker_fp
    assert same_chunks.version().embedding_fp == version.embedding_fp

    diff_collection = base.model_copy(update={'collection': 'c2'})
    diff_version = diff_collection.version()
    assert diff_version.collection == 'c2'
    assert diff_version.parser_fp == version.parser_fp


@pytest.mark.unit
def test_plan_flags_changes(digest_random):
    base = IngestionCreate.create(collection='c1', document_id=uuid4(), job_id=uuid4(), digest=digest_random)
    version = base.version()

    matching_record = cast(
        IngestionRecord,
        SimpleNamespace(
            parser_fp=version.parser_fp,
            chunker_fp=version.chunker_fp,
            embedding_fp=version.embedding_fp,
        ),
    )
    unchanged_plan = version.plan_for(matching_record)
    assert unchanged_plan.run_parser is False
    assert unchanged_plan.run_chunker is False
    assert unchanged_plan.run_embedding is False

    parser_changed = cast(
        IngestionRecord,
        SimpleNamespace(
            parser_fp='other',
            chunker_fp=version.chunker_fp,
            embedding_fp=version.embedding_fp,
        ),
    )
    parser_plan = version.plan_for(parser_changed)
    assert parser_plan.run_parser is True
    assert parser_plan.run_chunker is True
    assert parser_plan.run_embedding is True

    chunker_changed = cast(
        IngestionRecord,
        SimpleNamespace(
            parser_fp=version.parser_fp,
            chunker_fp='different',
            embedding_fp=version.embedding_fp,
        ),
    )
    chunker_plan = version.plan_for(chunker_changed)
    assert chunker_plan.run_parser is False
    assert chunker_plan.run_chunker is True
    assert chunker_plan.run_embedding is True

    embedding_changed = cast(
        IngestionRecord,
        SimpleNamespace(
            parser_fp=version.parser_fp,
            chunker_fp=version.chunker_fp,
            embedding_fp='alt',
        ),
    )
    embedding_plan = version.plan_for(embedding_changed)
    assert embedding_plan.run_parser is False
    assert embedding_plan.run_chunker is False
    assert embedding_plan.run_embedding is True
