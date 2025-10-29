from unittest.mock import AsyncMock, create_autospec

import pytest
from langchain_core.documents import Document

from parsers.docling import DoclingParser, DoclingParserConfig
from parsers.schemas import ParseResult

langchain_docling = pytest.importorskip('langchain_docling')
pytest.importorskip('docling_core.transforms.chunker.hybrid_chunker')
pytest.importorskip('tiktoken')

DoclingLoader = langchain_docling.DoclingLoader


@pytest.mark.asyncio
async def test_parse_success(tiny_pdf):
    """Test parsing a real PDF file."""

    loader = create_autospec(DoclingLoader, instance=True, spec_set=True)
    loader.aload = AsyncMock(return_value=[Document(page_content='Hello World', metadata={'source': 'unit://doc/1'})])
    parser = DoclingParser(config=DoclingParserConfig(), loader=loader)

    assert parser.loader == loader
    assert parser._parsed_docs is None
    result = await parser.parse(file=tiny_pdf)

    # Verify that documents were parsed
    assert isinstance(result, ParseResult)
    assert len(result.documents) == 1

    # Verify that each document has the expected structure
    for doc in result.documents:
        assert isinstance(doc, Document)
        assert doc.metadata['parser'] == 'DoclingParser'  # Parser should be set

    # Verify that the documents were cached
    assert parser._parsed_docs is not None
    assert parser._parsed_docs == result.documents
