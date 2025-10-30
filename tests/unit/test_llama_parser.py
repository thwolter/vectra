from types import SimpleNamespace
from typing import List

import pytest
from langchain_core.documents import Document

from vector.chunker import chunk_documents_by_headings
from vector.parser import LlamaParser


class _DummyLoader:
    def __init__(self, docs):
        self._docs = docs

    async def aload(self):
        return self._docs


@pytest.mark.asyncio
async def test_parse_success(tiny_pdf):
    """Test parsing a real PDF file using a mocked Llama loader."""

    loader = _DummyLoader([Document(page_content='Hello Llama', metadata={'source': 'unit://doc/llama/1'})])
    parser = LlamaParser(loader=loader)

    assert parser.loader == loader
    assert parser._parsed_docs is None

    result = await parser.parse(file=tiny_pdf)

    # Verify that documents were parsed
    assert isinstance(result, List)
    assert len(result) == 1

    # Verify that each document has the expected structure
    for doc in result:
        assert isinstance(doc, Document)
        assert doc.metadata['parser'] == 'LlamaParser'  # Parser should be set

    # Verify that the documents were cached
    assert parser._parsed_docs is not None
    assert parser._parsed_docs == result


def test_chunk_documents_by_headings(monkeypatch: pytest.MonkeyPatch):
    """Chunk documents with headings while leaving blank and heading-less docs untouched."""

    stub_settings = SimpleNamespace(text_splitter=SimpleNamespace(min_heading_level=2))
    monkeypatch.setattr('vector.parser.get_settings', lambda: stub_settings)

    docs = [
        Document(page_content='## Alpha\nAlpha body line', metadata={'source': 'unit://doc/alpha'}),
        Document(page_content='   ', metadata={'source': 'unit://doc/blank'}),
        Document(page_content='Plain paragraph without headings', metadata={'source': 'unit://doc/plain'}),
        Document(page_content='## Beta\nBeta body line', metadata={'source': 'unit://doc/beta'}),
    ]

    chunked = chunk_documents_by_headings(docs)

    assert len(chunked) == 4

    first, blank_doc, plain_doc, last = chunked

    assert first.metadata['header_title'] == 'Alpha'
    assert first.metadata['header_index'] == 0
    assert first.metadata['header_level'] == 2
    assert first.metadata['parser'] == 'LlamaParser'
    assert first.metadata['source'] == 'unit://doc/alpha'
    assert first.page_content.lstrip().startswith('## Alpha')

    assert blank_doc is docs[1]
    assert blank_doc.metadata == docs[1].metadata

    assert plain_doc is docs[2]
    assert plain_doc.metadata == docs[2].metadata

    assert last.metadata['header_title'] == 'Beta'
    assert last.metadata['header_index'] == 1
    assert last.metadata['header_level'] == 2
    assert last.metadata['parser'] == 'LlamaParser'
    assert last.metadata['source'] == 'unit://doc/beta'
    assert last.page_content.lstrip().startswith('## Beta')


def test_chunk_documents_by_headings_min_level_three(monkeypatch: pytest.MonkeyPatch):
    """Ensure only H3 sections create chunks when the minimum heading level is 3."""

    stub_settings = SimpleNamespace(text_splitter=SimpleNamespace(min_heading_level=3))
    monkeypatch.setattr('vector.parser.get_settings', lambda: stub_settings)

    docs = [
        Document(
            page_content='# Top Level\n\n## Mid Level\n\n### Deep Section\nDeep content line',
            metadata={'source': 'unit://doc/deep'},
        ),
        Document(
            page_content='# Heading without H3',
            metadata={
                'source': 'unit://doc/shallow',
                'parser': 'LlamaParser',
                'header_title': 'Heading without H3',
                'header_level': 1,
                'header_index': 1,
            },
        ),
    ]

    chunked = chunk_documents_by_headings(docs)

    assert len(chunked) == 2

    first_chunk = chunked[0]
    assert first_chunk.metadata['header_title'] == 'Deep Section'
    assert first_chunk.metadata['header_level'] == 3
    assert first_chunk.metadata['header_index'] == 0
    assert first_chunk.metadata['parser'] == 'LlamaParser'
    assert first_chunk.metadata['source'] == 'unit://doc/deep'
    assert first_chunk.page_content.lstrip().startswith('### Deep Section')

    # Second doc has no H3; it should remain untouched.
    assert chunked[1].page_content == docs[1].page_content
    assert chunked[1].metadata == docs[1].metadata


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
    parser = LlamaParser(loader=loader)

    result = await parser.parse(file=tiny_pdf)
    assert isinstance(result, List)

    assert len(result) == 4

    first, second, *_ = result
    assert first.metadata['parser'] == 'LlamaParser'
    assert second.metadata['parser'] == 'LlamaParser'

    assert first.metadata.get('header_title') == 'Document Title'
    assert first.metadata.get('header_level') == 1
    assert first.page_content.lstrip().startswith('# Document Title')

    assert second.metadata.get('header_title') == 'Section One'
    assert second.metadata.get('header_level') == 2
    assert second.page_content.lstrip().startswith('## Section One')
