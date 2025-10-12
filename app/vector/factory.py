from collections.abc import Callable
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from app.core.config import get_settings
from tenauth.tenancy import dsn_with_tenant
from app.vector.models import IngestorSettings

settings = get_settings()

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
    """Create a PGVector instance for the requested collection.

    - If an AsyncSession is provided, reuse its engine (tenant GUCs already applied).
    - Otherwise, construct using the configured DSN string.
    - No database I/O is performed here to keep this function sync-safe.
    """

    dsn = settings.pg_vector_url.get_secret_value()
    tenant_dsn = dsn_with_tenant(dsn, tenant_id)

    if not embeddings:
        provider = get_embeddings_provider(config.embedding_provider)
        embeddings = provider(config)

    return PGVector(
        connection=tenant_dsn,
        collection_name=collection,
        embeddings=embeddings,
    )
