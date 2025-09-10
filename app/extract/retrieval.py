from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore


async def retrieve(
    vs: VectorStore,
    query: str,
    *,
    digest: str,
    search_type: str = 'similarity',
    k: int = 6,
    fetch_k: int | None = None,
    score_threshold: Optional[float] = None,
    **extra: Any,
) -> List[Document]:
    kwargs: Dict[str, Any] = {'k': k, 'filter': {'digest': digest}}
    if fetch_k is not None:
        kwargs['fetch_k'] = fetch_k
    if score_threshold is not None:
        kwargs['score_threshold'] = score_threshold

    # Pass through additional search parameters such as lambda_mult for MMR
    kwargs.update(extra)
    # LangChain retriever supports similarity | mmr | similarity_score_threshold
    # and kwargs like k, fetch_k, lambda_mult, score_threshold, filter.  [oai_citation:4‡LangChain](https://python.langchain.com/api_reference/core/vectorstores/langchain_core.vectorstores.base.VectorStore.html?utm_source=chatgpt.com)
    # Use synchronous search to avoid requiring an AsyncEngine on PGVector instances.
    return vs.search(query=query, search_type=search_type, **kwargs)
