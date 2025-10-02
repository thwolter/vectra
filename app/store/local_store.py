from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, BinaryIO, cast
from uuid import UUID

from loguru import logger

from app.api.file import TemporaryUploadFile
from app.core.config import get_settings
from app.store.mixins import StoreKeyHelpers
from app.store.schemas import ArtifactInfo, FileInfo, StoredFiles

settings = get_settings()


def _resolve_fs_path(key: str) -> Path:
    # Keys are already rooted at base_path; make sure directories exist on write
    return Path(key)


def make_uri(key: str) -> str:
    return f'file://{_resolve_fs_path(key).resolve()}'


def _detect_content_attrs(name: str) -> tuple[str, str | None]:
    """Detect content type and encoding from a filename.

    Ensures a non-empty content_type; defaults to application/octet-stream.
    """
    lname = name.lower()
    if lname.endswith('.md'):
        return 'text/markdown; charset=utf-8', None
    if lname.endswith('.pdf.gz'):
        return 'application/pdf', 'gzip'
    if lname.endswith('.pdf'):
        return 'application/pdf', None
    return 'application/octet-stream', None


class LocalFileStore(StoreKeyHelpers):
    """Async local filesystem storage for document artifacts.

    Directory layout (relative keys):
        {base_path}/{collection}/{document_id}/
            - original{.ext | .ext.gz}
            - document.md

    Only storage/retrieval responsibilities are implemented.
    """

    def __init__(self, collection: str, *, base_path: str | Path | None = None) -> None:
        self.collection = collection
        self.base_path = str(base_path or settings.local_file_path)

    async def save_original(
        self,
        file: TemporaryUploadFile,
        *,
        document_id: UUID,
        compress: bool | None = None,
    ) -> ArtifactInfo:
        # Ensure we have a concrete UUID for key encoding

        ext = file.path.suffix or ''
        is_pdf = ext.lower() == '.pdf'
        gzip_enabled = bool(compress) and is_pdf

        key = self._original_key(document_id, ext, gzip_enabled=gzip_enabled)
        dest = _resolve_fs_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            if gzip_enabled:
                with open(file.path, 'rb') as f:
                    raw = f.read()
                data = gzip.compress(raw)
                dest.write_bytes(data)
            else:
                # Copy bytes
                with open(file.path, 'rb') as fsrc:
                    dest.write_bytes(fsrc.read())

            logger.success('Original saved locally')
            return ArtifactInfo(
                document_id=document_id,
                collection=self.collection,
                original_key=key,
                markdown_key=None,
            )
        except Exception as e:
            logger.error(
                'Failed to save original locally',
                extra={'error': str(e), 'key': key, 'document_id': str(document_id)},
            )
            raise

    async def save_markdown(
        self,
        md_text: str,
        *,
        document_id: UUID,
    ) -> ArtifactInfo:
        key = self._markdown_key(document_id)
        dest = _resolve_fs_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md_text, encoding='utf-8')
        logger.success('Markdown saved locally', extra={'key': key, 'document_id': str(document_id)})
        return ArtifactInfo(
            document_id=document_id,
            collection=self.collection,
            original_key=None,
            markdown_key=key,
        )

    async def delete(
        self,
        document_id: UUID,
        *,
        delete_original: bool = True,
        delete_markdown: bool = True,
    ) -> bool:
        prefix = self._prefix(document_id)
        base = _resolve_fs_path(prefix)
        try:
            if not base.exists():
                return True
            # Determine targets
            for p in base.iterdir():
                name = p.name
                if delete_original and name.startswith('original'):
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        logger.exception('Failed to delete file', extra={'path': str(p)})
                        return False
                if delete_markdown and name == 'document.md':
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        logger.exception('Failed to delete file', extra={'path': str(p)})
                        return False
            # Remove directory if empty
            try:
                if base.exists() and not any(base.iterdir()):
                    base.rmdir()
            except Exception:
                # Non-fatal if cannot remove dir
                pass
            return True
        except Exception as e:
            logger.error(
                'Failed to delete local artifacts',
                extra={'error': str(e), 'document_id': str(document_id)},
            )
            return False

    async def load(self, key: str) -> bytes:
        """Load a file by key and return its full content.

        Uses asyncio.to_thread to avoid blocking the event loop on disk I/O.
        """
        import asyncio

        path = _resolve_fs_path(key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f'Local object not found: {key}')

        def _read_all() -> bytes:
            with open(path, 'rb') as f:
                return f.read()

        return await asyncio.to_thread(_read_all)

    async def head(self, key: str) -> FileInfo:
        path = _resolve_fs_path(key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f'Local object not found: {key}')
        stat = path.stat()
        ctype, cenc = _detect_content_attrs(path.name)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        return FileInfo(
            key=key,
            size=stat.st_size,
            last_modified=last_modified,
            content_type=ctype,
            content_encoding=cenc,
            metadata={},
        )

    def stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        """Async streaming iterator for a local file without buffering fully."""
        import asyncio

        path = _resolve_fs_path(key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f'Local object not found: {key}')

        async def _gen() -> AsyncIterator[bytes]:
            f = cast(BinaryIO, await asyncio.to_thread(open, path, 'rb'))  # type: ignore['expected-type']
            try:
                while True:
                    chunk = await asyncio.to_thread(f.read, chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    await asyncio.to_thread(f.close)
                except OSError:
                    pass

        return _gen()

    async def info(self, document_id: UUID) -> StoredFiles:
        prefix = self._prefix(document_id)
        base = _resolve_fs_path(prefix)

        files: list[FileInfo] = []
        if base.exists() and base.is_dir():
            for p in base.iterdir():
                if p.is_file():
                    key = f'{prefix}{p.name}'
                    file_info = await self.head(key)
                    files.append(file_info)
        return StoredFiles(
            document_id=document_id,
            collection=self.collection,
            files=files,
        )
