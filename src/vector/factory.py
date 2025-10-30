from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from core.config import get_settings


def get_vectorstore(
    collection: str,
    *,
    tenant_id: UUID,
    embeddings: Embeddings | None = None,
) -> PGVector:
    """Create and return a PGVector instance lazily.

    This avoids importing DB drivers or creating connections at module import time,
    which helps tests and local dev that only import the graph.
    """
    dsn = get_settings().async_postgres_url.get_secret_value()

    if not embeddings:
        settings = get_settings()
        embeddings = OpenAIEmbeddings(model=settings.embedding.model)

    return PGVector(
        embeddings=embeddings,
        collection_name=collection,
        connection=dsn,
        async_mode=True,
        create_extension=False,
        engine_args={
            'connect_args': {'server_settings': {'app.tenant_id': str(tenant_id), 'search_path': 'vectra,public'}}
        },
    )
