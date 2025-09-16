# app/repositories/exceptions.py
class RecordNotFoundError(Exception):
    """Raised when a document row is not found in the repository."""

    pass


class RecordAlreadyExistsError(Exception):
    """Raised when a document row already exists in the repository."""

    pass


class RecordUpdateError(Exception):
    """Raised when a document row cannot be updated in the repository."""

    pass
