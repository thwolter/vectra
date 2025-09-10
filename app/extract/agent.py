from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.metadata.schemas import ProposedMetadata
from app.schemas.upload import UploadHints
from app.utils.types import SHA256B64
from app.vector.factory import get_vectorstore
from app.core.config import get_settings
from app.schemas.enums import CollectionEnum

from .graph import build_extract_graph
from app.metadata.base import Strategy


@lru_cache
def get_model():
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.doc_info_model_name,
        temperature=settings.doc_info_model_temperature,
    )


async def extract_metadata(
    digest: SHA256B64,
    collection: CollectionEnum,
    *,
    hints: UploadHints,
) -> ProposedMetadata:
    vs = get_vectorstore(collection=collection.value)
    llm = get_model()
    strategy = Strategy.from_hints(hints)
    query = strategy.retrieval_query()

    app = build_extract_graph(vs, llm, strategy)

    init = {
        'digest': digest,
        'collection': collection.value,
        'query': query,
        'attempt': 1,
        'max_attempts': 3,
    }

    state = await app.ainvoke(init)
    result = state.get('metadata')
    if not result:
        raise ValueError(f'Failed to extract metadata for digest {digest}')

    return result
