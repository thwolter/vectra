from langchain_core.documents import Document

from vector.batching import BatchBuilder
from vector.models import IngestorSettings


def test_empty_docs_returns_empty_batches():
    settings = IngestorSettings(max_tokens_per_request=100, max_docs_per_batch=2)
    bb = BatchBuilder(settings)
    assert bb.batch_documents_by_tokens([]) == []


def test_respects_max_docs_per_batch():
    settings = IngestorSettings(max_tokens_per_request=10_000, max_docs_per_batch=2)
    bb = BatchBuilder(settings)
    docs = [Document(page_content=f'doc{i}') for i in range(5)]

    batches = bb.batch_documents_by_tokens(docs)
    assert len(batches) == 3  # 2+2+1
    assert all(len(b) <= 2 for b in batches)
    assert sum(len(b) for b in batches) == len(docs)


def test_respects_max_tokens_and_skips_oversized():
    # estimate_tokens ~= len(text)//4
    settings = IngestorSettings(max_tokens_per_request=50, max_docs_per_batch=10)
    bb = BatchBuilder(settings)
    small = [Document(page_content='a' * 100) for _ in range(3)]  # ~25 tokens each
    huge = Document(page_content='x' * 1000)  # ~250 tokens -> skip

    batches = bb.batch_documents_by_tokens([small[0], huge, small[1], small[2]])
    # Should skip the huge doc and batch small docs by token cap: 2 per batch (25+25 <=50)
    assert sum(len(b) for b in batches) == 3
    # First batch likely 2 small docs, second batch 1 small doc
    assert any(len(b) == 2 for b in batches)
    assert any(len(b) == 1 for b in batches)
