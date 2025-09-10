from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from langchain_postgres import PGVector

settings = get_settings()


def _ensure_langchain_pg_compat() -> None:
    """Best-effort fix for older langchain_pg schema.

    Newer versions of langchain_postgres expect a JSONB column `cmetadata` on
    the `langchain_pg_collection` table. In CI or dev environments where this
    table already exists from an older version, selecting that column raises
    UndefinedColumn. We add it if missing. This is a no-op if the table doesn't
    exist yet (PG will ignore due to IF EXISTS), and it's safe if it already
    exists (IF NOT EXISTS).
    """
    try:
        import psycopg2  # type: ignore

        dsn = settings.pg_vector_url.get_secret_value()
        conn = psycopg2.connect(dsn)
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    'ALTER TABLE IF EXISTS langchain_pg_collection '
                    'ADD COLUMN IF NOT EXISTS cmetadata JSONB'
                )
                # Ensure embedding column exists on embedding table with typical dimension
                cur.execute(
                    'ALTER TABLE IF EXISTS langchain_pg_embedding '
                    'ADD COLUMN IF NOT EXISTS embedding vector(1536)'
                )
        finally:
            conn.close()
    except Exception:
        # Best effort only; PGVector will still attempt to create schema
        # and failures will surface in tests if truly fatal.
        pass


@lru_cache(maxsize=1)
def get_vectorstore(collection: str) -> 'PGVector':
    """
    Returns the vector instance.

    This function is used to access the vector for similarity search operations.
    """

    # Local imports = lazy
    from langchain_openai import OpenAIEmbeddings
    from langchain_postgres import PGVector
    from app.core.config import get_settings

    settings = get_settings()

    # Ensure compatible schema before PGVector inspects/creates collections
    _ensure_langchain_pg_compat()

    embedding = OpenAIEmbeddings(
        model=settings.embedding_model,
    )

    vectorstore = PGVector(
        connection=settings.pg_vector_url.get_secret_value(),
        collection_name=collection,
        embeddings=embedding,
    )

    return vectorstore
