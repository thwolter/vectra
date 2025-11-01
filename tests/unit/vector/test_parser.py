from typing import List

import pytest
from langchain_core.documents import Document

from vector.parser import LlamaParser


class _DummyLoader:
    def __init__(self, docs):
        self._docs = docs

    async def aload(self):
        return self._docs


@pytest.mark.asyncio
async def test_parse_success(tiny_pdf):
    """Parse a real PDF using a dummy loader and ensure metadata is applied."""

    loader = _DummyLoader([Document(page_content='Hello Llama', metadata={'source': 'unit://doc/llama/1'})])
    parser = LlamaParser(loader=loader)

    assert parser.loader == loader
    assert parser._parsed_docs is None

    result = await parser.parse(file=tiny_pdf)

    assert isinstance(result, List)
    assert len(result) == 1

    doc = result[0]
    assert isinstance(doc, Document)
    assert doc.metadata['parser'] == 'LlamaParser'

    assert parser._parsed_docs == result
