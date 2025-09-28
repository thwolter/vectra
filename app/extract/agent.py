from __future__ import annotations

from langchain_openai import ChatOpenAI
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.metadata.base import Strategy
from app.metadata.config import ExtractConfig
from app.metadata.schemas import ProposedMetadata
from app.schemas.upload import UploadHints
from app.utils.types import SHA256B64
from app.vector.factory import get_vectorstore
from app.vector.models import IngestorSettings

from .graph import build_extract_graph
from loguru import logger

def get_model(config: ExtractConfig):
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=config.model_name,
        temperature=config.temperature,
    )


async def extract_metadata(
    session: AsyncSession,
    *,
    digest: SHA256B64,
    collection: str,
    ingestor_config: IngestorSettings,
    extract_config: ExtractConfig,
    hints: UploadHints,
) -> ProposedMetadata:
    tenant_id = session.info['tenant_id']
    vs = get_vectorstore(collection=collection, tenant_id=tenant_id, config=ingestor_config)
    llm = get_model(config=extract_config)
    strategy = Strategy.from_hints(hints)
    query = strategy.retrieval_query()
    if not query:
        logger.debug(f'No retrieval query generated for strategy {strategy}')
        return ProposedMetadata()

    app = build_extract_graph(vs, llm, strategy)

    init = {
        'digest': digest,
        'collection': collection,
        'query': query,
        'attempt': 1,
        'max_attempts': extract_config.max_attempts,
    }

    state = await app.ainvoke(init)
    result = state.get('metadata')
    if not result:
        raise ValueError(f'Failed to extract metadata for digest {digest}')

    return result
