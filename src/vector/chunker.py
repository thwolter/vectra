from __future__ import annotations

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from core.config import get_settings


def get_header_name(level: int) -> str:
    return f'Header {level}'


def chunk_documents_by_headings(docs: List[Document]) -> List[Document]:
    settings = get_settings()
    min_level = getattr(settings.text_splitter, 'min_heading_level', 1)
    max_level = getattr(settings.text_splitter, 'max_heading_level', 6)

    headers_to_split_on = [('#' * level, get_header_name(level)) for level in range(min_level, max_level + 1)]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)

    new_docs: List[Document] = []
    for doc in docs:
        text = doc.page_content or ''
        if not text.strip():
            new_docs.append(doc)
            continue
        chunks = splitter.split_text(text)
        new_docs += chunks

    return new_docs
