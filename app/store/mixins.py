from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID


class StoreKeyHelpers:
    """Mixin providing common key-building helpers for stores.

    This mixin is storage-agnostic and only deals with deterministic key
    construction based on the configured base_path, collection and document_id.
    Concrete stores (S3, local FS, etc.) can inherit this alongside
    `DocumentStore` to reuse the helpers.
    """

    collection: str
    base_path: str

    @staticmethod
    def _encode_document_id(document_id: UUID) -> str:
        """Encode the document_id as URL-safe base64 without padding.

        Accepts a UUID instance or a string representation of a UUID. Raises
        ValueError if the value cannot be interpreted as a UUID.
        """
        return base64.urlsafe_b64encode(document_id.bytes).decode('ascii').rstrip('=')

    def _prefix(self, document_id: UUID) -> str:
        """Return the key prefix for a given document_id using urlsafe base64 encoding.

        The document_id may be provided as a UUID instance or a string UUID. The encoded
        value is padding-stripped to keep keys concise.
        """
        encoded = self._encode_document_id(document_id)
        return f'{self.base_path}/{self.collection}/{encoded}/'

    def _original_key(self, document_id: UUID, ext: str, *, gzip_enabled: bool) -> str:
        """Return the original file key, with optional .gz suffix for compressed uploads.

        Args:
            document_id: Target document id.
            ext: File extension including leading dot (e.g., ".pdf") or empty string.
            gzip_enabled: Whether gzip compression will be applied client-side.
        """
        if gzip_enabled and ext:
            return f'{self._prefix(document_id)}original{ext}.gz'
        return f'{self._prefix(document_id)}original{ext}'

    def _markdown_key(self, document_id: UUID) -> str:
        """Return the markdown artifact key for a document."""
        return f'{self._prefix(document_id)}document.md'

    @staticmethod
    def _ext_for_path(file_path: str) -> str:
        """Return lowercase suffix for a path (including the dot) or empty string."""
        return (Path(file_path).suffix or '').lower()

    @staticmethod
    def _is_pdf_ext(ext: str) -> bool:
        return ext.lower() == '.pdf'
