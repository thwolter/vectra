from app.core.dependencies import get_database_manager
from .documents import DocumentRepository
from .ingestion_repository import IngestionVersions
from .job_repository import JobRepository
from .embeddings import EmbeddingsRepository


def get_embedding_repository() -> EmbeddingsRepository:
    """Create a MetadataRepository bound to the global DatabaseManager."""
    return EmbeddingsRepository(get_database_manager())


def get_ingestion_repository() -> IngestionVersions:
    """Create an IngestionRepository bound to the global DatabaseManager."""
    return IngestionVersions(get_database_manager())


def get_document_repository() -> DocumentRepository:
    """Create a DocumentRepository bound to the global DatabaseManager."""
    return DocumentRepository(get_database_manager())


def get_job_repository() -> JobRepository:
    """Create a JobRepository bound to the global DatabaseManager."""
    return JobRepository(get_database_manager())
