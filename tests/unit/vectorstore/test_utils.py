import pytest
from langchain_core.documents import Document

from app.vector.utils import estimate_docs_tokens, validate_docs


def test_estimate_tokens_sums_over_docs():
    docs = [
        Document(page_content='a' * 8, metadata={}),
        Document(page_content='b' * 100, metadata={}),
        Document(page_content='', metadata={}),
    ]
    assert estimate_docs_tokens(docs) > 0


@pytest.mark.asyncio
def test_validate_docs_filters_missing_fields(digest_str):
    valid_doc = Document(page_content='hello', metadata={})
    also_valid = Document(page_content='hello', metadata={})
    empty_content = Document(page_content='   ', metadata={})
    # Also ensure robustness if metadata isn't a dict
    weird_meta = Document(page_content='world')
    docs = [valid_doc, also_valid, empty_content, weird_meta]

    valid, errors = validate_docs(docs)

    assert valid == [valid_doc, also_valid, weird_meta]
    assert len(errors) == 1
    assert any('missing page_content' in e for e in errors)
