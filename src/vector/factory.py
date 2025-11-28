from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import DistanceStrategy

from core.config import get_settings
from vector.tenant_pgvector import TenantAwarePGVector


def get_vectorstore(
    collection: str,
    *,
    tenant_id: UUID,
    embeddings: Embeddings | None = None,
) -> TenantAwarePGVector:
    """Create and return a PGVector instance lazily.

    This avoids importing DB drivers or creating connections at module import time,
    which helps tests and local dev that only import the graph.
    """
    settings = get_settings()
    dsn = settings.async_postgres_url.get_secret_value()

    if not embeddings:
        embeddings = OpenAIEmbeddings(model=settings.embedding.model)

    engine_args = {
        'pool_size': settings.db_pool_size,
        'max_overflow': settings.db_max_overflow,
        'pool_timeout': settings.db_pool_timeout,
        'pool_pre_ping': True,
        'connect_args': {
            'server_settings': {
                'app.tenant_id': str(tenant_id),
                'search_path': f'{settings.db_schema},public',
            },
            'statement_cache_size': 0,
        },
    }

    return TenantAwarePGVector(
        embeddings=embeddings,
        collection_name=collection,
        connection=dsn,
        async_mode=True,
        create_extension=False,
        distance_strategy=DistanceStrategy.COSINE,
        engine_args=engine_args,
    )
