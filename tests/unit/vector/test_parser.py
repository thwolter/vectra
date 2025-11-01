import sys
import types
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


@pytest.mark.asyncio
async def test_parse_uses_markdown_documents(monkeypatch, tiny_pdf):
    """Ensure the default LlamaParser integration requests markdown output."""

    from core.config import get_settings

    monkeypatch.setenv('LLAMA_CLOUD__API_KEY', 'dummy-key')
    get_settings.cache_clear()

    class _MarkdownDoc:
        def __init__(self, text: str):
            self.text = text
            self.metadata = {'source': 'unit://doc/markdown/1'}

    class _ParseResult:
        called = False

        def get_markdown_documents(self):
            type(self).called = True
            return [_MarkdownDoc('# Heading\nBody text')]

    class _FakeLlamaParse:
        last_called_with: str | None = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def parse(self, file_path: str):
            type(self).last_called_with = file_path
            return _ParseResult()

    fake_module = types.SimpleNamespace(LlamaParse=_FakeLlamaParse)
    monkeypatch.setitem(sys.modules, 'llama_parse', fake_module)

    parser = LlamaParser()
    docs = await parser.parse(file=tiny_pdf)

    assert _FakeLlamaParse.last_called_with == tiny_pdf
    assert _ParseResult.called is True

    assert docs[0].page_content == '# Heading\nBody text'
    assert docs[0].metadata['parser'] == 'LlamaParser'
    assert docs[0].metadata['node_index'] == 0
    assert docs[0].metadata['source'] == 'unit://doc/markdown/1'

    markdown = await parser.to_markdown()
    assert markdown == '# Heading\nBody text'

    get_settings.cache_clear()
