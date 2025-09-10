from unittest.mock import create_autospec, AsyncMock

import pytest
from langchain_core.documents import Document
from langchain_docling import DoclingLoader

from app.parsers.docling import DoclingParser
from app.parsers.schemas import ParseResult


@pytest.mark.asyncio
async def test_initialize_success(tiny_pdf):
    """Test initialization of DoclingParser."""
    parser = DoclingParser(file=tiny_pdf)
    assert parser.file == tiny_pdf
    assert hasattr(parser, 'loader')
    assert parser._parsed_docs is None


@pytest.mark.asyncio
async def test_parse_success(tiny_pdf):
    """Test parsing a real PDF file."""

    loader = create_autospec(DoclingLoader, instance=True, spec_set=True)
    loader.aload = AsyncMock(
        return_value=[
            Document(page_content='Hello World', metadata={'source': 'unit://doc/1'})
        ]
    )
    parser = DoclingParser(file=tiny_pdf, loader=loader)

    assert parser.loader == loader
    assert parser._parsed_docs is None
    result = await parser.parse()

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
