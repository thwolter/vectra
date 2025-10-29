from vector.ingestor import DocumentIngestor
from vector.models import IngestorSettings


def default_ingestor_provider(*, collection: str, config: IngestorSettings) -> DocumentIngestor:
    """Provide a DocumentIngestor with injected settings for the given collection."""
    return DocumentIngestor(collection=collection, config=config)
