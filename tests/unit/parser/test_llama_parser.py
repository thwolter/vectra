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


@pytest.mark.asyncio
async def test_heading_chunking_splits_sections(tiny_pdf):
    """Llama parser should split markdown into chunks by section headings (## and deeper)."""

    md = (
        '# Document Title\n\n'
        'Intro text that should remain with the first section or be ignored if no H2 exists.\n\n'
        '## Section One\n'
        'Content A line 1.\n\n'
        '### Sub A\n'
        'Details under sub A.\n\n'
        '## Section Two\n'
        'Content B line 1.\n'
    )

    loader = _DummyLoader([Document(page_content=md, metadata={'source': 'unit://doc/llama/2'})])
    parser = LlamaParser(config=LlamaParserConfig(heading_chunking_enabled=True, min_heading_level=2), loader=loader)

    result = await parser.parse(file=tiny_pdf)
    assert isinstance(result, ParseResult)

    # Expect two chunks (split on the two H2 sections). The H3 stays within Section One
    assert len(result.documents) == 2

    first, second = result.documents
    assert first.metadata['parser'] == 'LlamaParser'
    assert second.metadata['parser'] == 'LlamaParser'

    assert first.metadata.get('section_title') == 'Section One'
    assert first.metadata.get('section_level') == 2
    assert first.page_content.lstrip().startswith('## Section One')

    assert second.metadata.get('section_title') == 'Section Two'
    assert second.metadata.get('section_level') == 2
    assert second.page_content.lstrip().startswith('## Section Two')
