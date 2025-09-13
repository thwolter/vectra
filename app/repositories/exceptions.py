# app/repositories/exceptions.py
class DocumentNotFoundError(Exception):
    """Raised when a document row is not found in the repository."""

    pass


class DocumentAlreadyExistsError(Exception):
    """Raised when a document row already exists in the repository."""

    pass


class DocumentUpdateError(Exception):
    """Raised when a document row cannot be updated in the repository."""

    pass


class JobNotFoundError(Exception):
    """Raised when a job row is not found in the repository."""

    pass


class IngestionNotFoundError(Exception):
    """Raised when an ingestion row is not found in the repository."""

    pass


class IngestionAlreadyExistsError(Exception):
    """Raised when an ingestion row already exists in the repository."""

    pass
