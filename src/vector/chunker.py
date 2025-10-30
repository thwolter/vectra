from __future__ import annotations

import re
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from core.config import get_settings


def get_header_name(level: int) -> str:
    return f'Header {level}'


def _normalize_chunk_content(content: str, level: int) -> str:
    """Trim a markdown chunk so it starts at the heading for the detected level."""
    if not content:
        return content

    heading_prefix = '#' * level
    # Allow optional leading whitespace and capture the heading sans indentation.
    pattern = re.compile(rf'^[ \t]*(?P<heading>{re.escape(heading_prefix)}[^\n]*)', re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return content.lstrip()
    return content[match.start('heading') :]


def chunk_documents_by_headings(docs: List[Document]) -> List[Document]:
    settings = get_settings()
    min_level = getattr(settings.text_splitter, 'min_heading_level', 1)
    max_level = getattr(settings.text_splitter, 'max_heading_level', 6)

    headers_to_split_on = [('#' * level, get_header_name(level)) for level in range(min_level, max_level + 1)]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    new_docs: List[Document] = []
    section_index = 0

    for doc in docs:
        text = doc.page_content or ''
        if not text.strip():
            new_docs.append(doc)
            continue

        chunks = splitter.split_text(text)
        heading_chunks: List[tuple[int, str, dict]] = []
        leftover_contents: List[str] = []

        for chunk in chunks:
            title = None
            level = None
            for candidate_level in range(max_level, min_level - 1, -1):
                candidate_key = get_header_name(candidate_level)
                candidate_value = chunk.metadata.get(candidate_key)
                if candidate_value:
                    title = candidate_value
                    level = candidate_level
                    break

            if not title or level is None or level < min_level:
                if chunk.page_content and chunk.page_content.strip():
                    leftover_contents.append(chunk.page_content)
                continue

            md = dict(doc.metadata)
            md.update(
                {
                    'parser': 'LlamaParser',
                    'header_title': title.strip(),
                    'header_level': level,
                }
            )
            normalized_content = _normalize_chunk_content(chunk.page_content, level)
            heading_chunks.append((level, normalized_content, md))

        if heading_chunks:
            primary_level_docs = [hc for hc in heading_chunks if hc[0] == min_level]
            other_heading_docs = [hc for hc in heading_chunks if hc[0] != min_level]

            for level, content, md in primary_level_docs + other_heading_docs:
                metadata = dict(md)
                metadata['header_index'] = section_index
                section_index += 1
                new_docs.append(Document(page_content=content, metadata=metadata))

            for content in leftover_contents:
                if not content.strip():
                    continue
                md = dict(doc.metadata)
                md.setdefault('parser', 'LlamaParser')
                new_docs.append(Document(page_content=content, metadata=md))
        else:
            new_docs.append(doc)

    return new_docs
