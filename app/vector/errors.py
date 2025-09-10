class EmbeddingsAlreadyExistError(Exception):
    """Raised when trying to ingest documents for a digest that already has embeddings."""

    pass
