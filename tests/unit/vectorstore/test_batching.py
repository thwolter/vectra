from langchain_core.documents import Document

from core.config import get_settings
from vector.batching import batch_documents_by_tokens


def test_empty_docs_returns_empty_batches():
    assert batch_documents_by_tokens([]) == []


def test_respects_max_docs_per_batch():
    get_settings.cache_clear()
    settings = get_settings()
    settings.embedding.max_docs_per_batch = 2

    docs = [Document(page_content=f'doc{i}') for i in range(5)]

    batches = batch_documents_by_tokens(docs)
    assert len(batches) == 3  # 2+2+1
    assert all(len(b) <= 2 for b in batches)
    assert sum(len(b) for b in batches) == len(docs)


def test_respects_max_tokens_and_skips_oversized():
    # estimate_tokens ~= len(text)//4
    get_settings.cache_clear()
    settings = get_settings()
    settings.embedding.max_tokens_per_request = 50
    small = [Document(page_content='a' * 100) for _ in range(3)]  # ~25 tokens each
    huge = Document(page_content='x' * 1000)  # ~250 tokens -> skip

    batches = batch_documents_by_tokens([small[0], huge, small[1], small[2]])
    # Should skip the huge doc and batch small docs by token cap: 2 per batch (25+25 <=50)
    assert sum(len(b) for b in batches) == 3
    # First batch likely 2 small docs, second batch 1 small doc
    assert any(len(b) == 2 for b in batches)
    assert any(len(b) == 1 for b in batches)
