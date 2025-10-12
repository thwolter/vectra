import pytest
from langchain_core.documents import Document

from app.parsers.llama import LlamaParser, LlamaParserConfig
from app.parsers.schemas import ParseResult


class _DummyLoader:
    def __init__(self, docs):
        self._docs = docs

    async def aload(self):
        return self._docs


@pytest.mark.asyncio
async def test_parse_success(tiny_pdf):
    """Test parsing a real PDF file using a mocked Llama loader."""

    loader = _DummyLoader([Document(page_content='Hello Llama', metadata={'source': 'unit://doc/llama/1'})])
    parser = LlamaParser(config=LlamaParserConfig(), loader=loader)

    assert parser.loader == loader
    assert parser._parsed_docs is None

    result = await parser.parse(file=tiny_pdf)

    # Verify that documents were parsed
    assert isinstance(result, ParseResult)
    assert len(result.documents) == 1

    # Verify that each document has the expected structure
    for doc in result.documents:
        assert isinstance(doc, Document)
        assert doc.metadata['parser'] == 'LlamaParser'  # Parser should be set

    # Verify that the documents were cached
    assert parser._parsed_docs is not None
    assert parser._parsed_docs == result.documents
