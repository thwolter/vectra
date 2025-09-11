from app.schemas.enums import CollectionEnum
from app.vector.ingestor import DocumentIngestor


def default_ingestor_provider(*, collection: CollectionEnum) -> DocumentIngestor:
    # embedding_profile is currently unused by DocumentIngestor constructor; kept for API compatibility
    return DocumentIngestor(collection=collection.value)
