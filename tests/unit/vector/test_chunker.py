from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from core.config import get_settings
from vector.chunker import chunk_documents_by_headings


def _stub_text_splitter(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    """Copy current text splitter settings and override provided values."""

    settings = get_settings()
    text_splitter = settings.text_splitter
    stub_settings = SimpleNamespace(
        text_splitter=SimpleNamespace(
            min_heading_level=overrides.get('min_heading_level', text_splitter.min_heading_level),
            max_heading_level=overrides.get('max_heading_level', text_splitter.max_heading_level),
        )
    )
    monkeypatch.setattr('vector.chunker.get_settings', lambda: stub_settings)


def test_chunk_documents_by_headings(monkeypatch: pytest.MonkeyPatch):
    """Chunk documents with headings while leaving blank and heading-less docs untouched."""

    _stub_text_splitter(monkeypatch, min_heading_level=2)

    docs = [
        Document(page_content='## Alpha\nAlpha body line', metadata={'source': 'unit://doc/alpha'}),
        Document(page_content='   ', metadata={'source': 'unit://doc/blank'}),
        Document(page_content='Plain paragraph without headings', metadata={'source': 'unit://doc/plain'}),
        Document(page_content='## Beta\nBeta body line', metadata={'source': 'unit://doc/beta'}),
    ]

    chunked = chunk_documents_by_headings(docs)

    assert len(chunked) == 4

    first, blank_doc, plain_doc, last = chunked

    assert first.metadata['Header 2'] == 'Alpha'
    assert first.page_content.lstrip().startswith('## Alpha')

    assert blank_doc is docs[1]
    assert blank_doc.metadata == docs[1].metadata

    assert last.metadata['Header 2'] == 'Beta'
    assert last.page_content.lstrip().startswith('## Beta')


def test_chunk_documents_by_headings_min_level_three(monkeypatch: pytest.MonkeyPatch):
    """Ensure only H3 sections create chunks when the minimum heading level is 3."""

    _stub_text_splitter(monkeypatch, min_heading_level=3)

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
    assert first_chunk.metadata['Header 3'] == 'Deep Section'
    assert first_chunk.page_content.lstrip().startswith('# Top Level')

    # Second doc has no H3; it should remain untouched.
    assert chunked[1].page_content == docs[1].page_content
    assert chunked[1].metadata == {}


def test_heading_chunking_splits_sections(monkeypatch: pytest.MonkeyPatch):
    """Chunk markdown headings according to current splitter settings."""

    _stub_text_splitter(monkeypatch)

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

    docs = [Document(page_content=md, metadata={'source': 'unit://doc/llama/2'})]

    chunked = chunk_documents_by_headings(docs)

    assert len(chunked) == 4

    first, second, third, fourth = chunked

    assert first.metadata.get('Header 1') == 'Document Title'
    assert first.page_content.lstrip().startswith('# Document Title')

    assert second.metadata.get('Header 1') == 'Document Title'
    assert second.metadata.get('Header 2') == 'Section One'
    assert second.page_content.lstrip().startswith('## Section One')

    assert third.metadata.get('Header 1') == 'Document Title'

    assert fourth.metadata.get('Header 2') == 'Section Two'
    assert fourth.page_content.lstrip().startswith('## Section Two')
