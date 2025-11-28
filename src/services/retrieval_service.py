from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from tenauth.schemas import AccessContext

from core.db import scoped_session
from repositories import embeddings_repository
from schemas.search import ChunkSearchRequest, ChunkSearchResponse, ChunkSearchResult
from vector.factory import get_vectorstore


def _chunk_id_from_metadata(metadata: dict[str, Any]) -> str | None:
    for key in ('chunk_id', 'chunkId', 'id'):
        value = metadata.get(key)
        if value is not None:
            return str(value)
    return None


class RetrievalService:
    async def search(self, *, payload: ChunkSearchRequest, access: AccessContext) -> ChunkSearchResponse:
        collection_exists = await self._collection_exists(collection=payload.collection, access=access)
        if not collection_exists:
            return ChunkSearchResponse(results=[], collection_exists=False)

        vectorstore = get_vectorstore(collection=payload.collection, tenant_id=access.tenant_id)
        filters = payload.build_filter()
        kwargs: dict[str, Any] = {'k': payload.limit}
        if filters:
            kwargs['filter'] = filters

        raw_results: list[tuple[Document, float]] = await vectorstore.asimilarity_search_with_score(
            payload.query,
            **kwargs,
        )

        matches: list[ChunkSearchResult] = []
        for doc, score in raw_results:
            metadata = dict(doc.metadata or {})
            match = ChunkSearchResult(
                chunk_id=_chunk_id_from_metadata(metadata),
                text=doc.page_content,
                metadata=metadata,
                score=float(score),
            )
            matches.append(match)

        if payload.score_threshold is not None:
            matches = [match for match in matches if match.score >= payload.score_threshold]

        return ChunkSearchResponse(results=matches, collection_exists=True)

    async def _collection_exists(self, *, collection: str, access: AccessContext) -> bool:
        async with scoped_session(access_context=access) as session:
            return await embeddings_repository.collection_exists(session, collection=collection)


__all__ = ['RetrievalService']
