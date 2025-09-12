# app/repositories/exceptions.py
class DocumentNotFoundError(Exception):
    """Raised when a document row is not found in the repository."""

    pass
