from __future__ import annotations

import base64
import binascii
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
    def _encode_identifier(value: UUID | str | bytes) -> str:
        """Encode UUID/bytes/strings using url-safe base64 without padding.

        Strings are decoded from base64 first when possible to minimize output length.
        """
        if isinstance(value, UUID):
            raw = value.bytes
        elif isinstance(value, bytes):
            raw = value
        else:
            candidate = value.encode('utf-8')
            try:
                raw = base64.b64decode(StoreKeyHelpers._ensure_base64_padding(value), altchars=b'-_')
            except binascii.Error:
                raw = candidate
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

    @staticmethod
    def _ensure_base64_padding(value: str) -> str:
        padding = '=' * (-len(value) % 4)
        return value + padding

    def _prefix(self, *, tenant_id: UUID, digest: str) -> str:
        """Return the key prefix for a given tenant/digest scope.

        Keys are namespaced as:
            {base_path}/{tenant}/{collection}/{digest}/
        """
        tenant_component = self._encode_identifier(tenant_id)
        digest_component = self._encode_identifier(digest)
        return f'{self.base_path}/{tenant_component}/{self.collection}/{digest_component}/'

    def _original_key(
        self,
        *,
        tenant_id: UUID,
        digest: str,
        ext: str,
        gzip_enabled: bool,
    ) -> str:
        """Return the original file key, with optional .gz suffix for compressed uploads.

        Args:
            tenant_id: Tenant the document belongs to.
            digest: Stable digest identifier for the document.
            ext: File extension including leading dot (e.g., ".pdf") or empty string.
            gzip_enabled: Whether gzip compression will be applied client-side.
        """
        prefix = self._prefix(tenant_id=tenant_id, digest=digest)
        if gzip_enabled and ext:
            return f'{prefix}original{ext}.gz'
        return f'{prefix}original{ext}'

    def _markdown_key(self, *, tenant_id: UUID, digest: str) -> str:
        """Return the markdown artifact key for a document."""
        return f'{self._prefix(tenant_id=tenant_id, digest=digest)}document.md'

    @staticmethod
    def _ext_for_path(file_path: str) -> str:
        """Return lowercase suffix for a path (including the dot) or empty string."""
        return (Path(file_path).suffix or '').lower()

    @staticmethod
    def _is_pdf_ext(ext: str) -> bool:
        return ext.lower() == '.pdf'
