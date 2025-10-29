from collections.abc import Callable
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from core.config import get_settings
from vector.models import IngestorSettings

EmbeddingFactory = Callable[[IngestorSettings], Embeddings]
EMBEDDING_PROVIDERS: dict[str, EmbeddingFactory] = {}


def register_embeddings_provider(name: str, factory: EmbeddingFactory) -> None:
    EMBEDDING_PROVIDERS[name] = factory


def get_embeddings_provider(name: str) -> EmbeddingFactory:
    try:
        return EMBEDDING_PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f'Unknown embeddings provider: {name!r}') from exc


def _openai_embeddings_factory(config: IngestorSettings) -> Embeddings:
    return OpenAIEmbeddings(
        model=config.embed_model,
    )


register_embeddings_provider('openai', _openai_embeddings_factory)


def get_vectorstore(
    collection: str,
    *,
    tenant_id: UUID,
    config: IngestorSettings,
    embeddings: Embeddings | None = None,
) -> PGVector:
    """Create and return a PGVector instance lazily.

    This avoids importing DB drivers or creating connections at module import time,
    which helps tests and local dev that only import the graph.
    """
    dsn = get_settings().async_postgres_url.get_secret_value()

    if not embeddings:
        provider = get_embeddings_provider(config.embedding_provider)
        embeddings = provider(config)

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
