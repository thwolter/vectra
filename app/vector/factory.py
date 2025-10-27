import inspect
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from tenauth.tenancy import dsn_with_tenant

from app.core.config import get_settings
from app.core.db_schema import APP_SCHEMA
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


def _ensure_search_path_in_dsn(dsn: str) -> str:
    """Append a search_path option that prioritizes the application schema."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parsed = urlparse(dsn)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    search_flag = f'-csearch_path={APP_SCHEMA},public'

    updated = False
    for idx, (key, value) in enumerate(query_pairs):
        if key == 'options':
            if f'-csearch_path={APP_SCHEMA}' in value:
                updated = True
                break
            query_pairs[idx] = (key, f'{value} {search_flag}'.strip())
            updated = True
            break

    if not updated:
        query_pairs.append(('options', search_flag))

    new_query = urlencode(query_pairs, doseq=True)
    return cast(str, urlunparse(parsed._replace(query=new_query)))


def _pgvector_supports_schema() -> bool:
    try:
        signature = inspect.signature(PGVector.__init__)
    except (TypeError, ValueError):
        return False
    return 'schema_name' in signature.parameters


_PGVECTOR_KWARGS: dict[str, Any] = {'schema_name': APP_SCHEMA} if _pgvector_supports_schema() else {}


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

    dsn = settings.postgres_url.get_secret_value()
    tenant_dsn = dsn_with_tenant(dsn, tenant_id)
    tenant_dsn = _ensure_search_path_in_dsn(tenant_dsn)

    if not embeddings:
        provider = get_embeddings_provider(config.embedding_provider)
        embeddings = provider(config)

    return PGVector(
        connection=tenant_dsn,
        collection_name=collection,
        embeddings=embeddings,
        **_PGVECTOR_KWARGS,
    )
