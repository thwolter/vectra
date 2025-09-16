from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.metadata.base import Strategy
from app.metadata.schemas import ProposedMetadata
from app.schemas.enums import CollectionEnum
from app.schemas.upload import UploadHints
from app.utils.types import SHA256B64
from app.vector.factory import get_vectorstore

from .graph import build_extract_graph


@lru_cache
def get_model():
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.doc_info_model_name,
        temperature=settings.doc_info_model_temperature,
    )


async def extract_metadata(
    session: AsyncSession,
    *,
    digest: SHA256B64,
    collection: CollectionEnum,
    hints: UploadHints,
) -> ProposedMetadata:
    tenant_id = session.info['tenant_id']
    vs = get_vectorstore(collection=collection.value, tenant_id=tenant_id)
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
