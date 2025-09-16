from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from app.core.config import get_settings
from app.core.tenancy import dsn_with_tenant

settings = get_settings()


def get_vectorstore(
    collection: str,
    *,
    tenant_id: UUID,
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
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
        )

    return PGVector(
        connection=tenant_dsn,
        collection_name=collection,
        embeddings=embeddings,
    )
