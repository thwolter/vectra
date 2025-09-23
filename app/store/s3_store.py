from __future__ import annotations

import gzip
import tempfile
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import UUID

import aioboto3
from loguru import logger

from app.api.file import TemporaryUploadFile
from app.core.config import get_settings
from app.store.mixins import StoreKeyHelpers
from app.store.schemas import ArtifactInfo, FileInfo, StoredFiles

settings = get_settings()


def get_client():
    session = aioboto3.Session()
    return session.client('s3', region_name=settings.aws_region)


class S3Store(StoreKeyHelpers):
    def __init__(self, collection: str, *, base_path: str | Path | None = None):
        self.collection = collection
        self.base_path = str(base_path or settings.aws_s3_path)
        self.client_factory = get_client

    def make_uri(self, key: str) -> str:
        return f's3://{settings.aws_s3_bucket}/{key}'

    async def save_original(
        self,
        file: TemporaryUploadFile,
        *,
        document_id: UUID,
        compress: bool | None = None,
    ) -> ArtifactInfo:
        ext = (Path(file.filename).suffix or '').lower()
        is_pdf = ext == '.pdf'
        gzip_enabled = bool(compress) and is_pdf

        key = self._original_key(document_id, ext, gzip_enabled=gzip_enabled)

        async with self.client_factory() as s3:
            with open(file.path, 'rb') as f:
                logger.debug(f'Uploading {file.filename} to S3')
                extra_args: dict[str, Any] = {'ContentType': file.content_type}
                f.seek(0)
                try:
                    CHUNK_SIZE = 1024 * 1024  # 1 MiB
                    tmp = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
                    try:
                        if gzip_enabled:
                            extra_args['ContentEncoding'] = 'gzip'
                            with gzip.GzipFile(fileobj=tmp, mode='wb') as gz:
                                while True:
                                    chunk = f.read(CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    gz.write(chunk)
                        else:
                            while True:
                                chunk = f.read(CHUNK_SIZE)
                                if not chunk:
                                    break
                                tmp.write(chunk)

                        # We own the buffer; upload from it
                        tmp.seek(0)
                        await s3.upload_fileobj(tmp, settings.aws_s3_bucket, key, ExtraArgs=extra_args)
                    finally:
                        try:
                            tmp.close()
                        except Exception:
                            pass

                    logger.success(
                        'Original uploaded to S3',
                        extra={'key': key, 'document_id': document_id},
                    )
                    return ArtifactInfo(
                        document_id=document_id,
                        collection=self.collection,
                        original_key=key,
                        markdown_key=None,
                    )
                except Exception as e:
                    logger.error('Failed to upload original to S3')
                    raise e

    async def save_markdown(
        self,
        md_text: str,
        *,
        document_id: UUID,
    ) -> ArtifactInfo:
        """Save a markdown copy to S3 for a given document_id.

        The markdown is encoded as UTF-8 and uploaded with a `text/markdown; charset=utf-8`
        Content-Type. Existing object with the same key is overwritten.

        Args:
            md_text: Markdown content to upload.
            document_id: Target document identifier. It should match that of the original.
            extra_metadata: Optional user metadata to attach to the object.

        Returns:
            ArtifactInfo: Result object with document_id and the S3 key to the uploaded markdown.

        Raises:
            Exception: Propagates underlying aioboto3/botocore exceptions.
        """
        key = self._markdown_key(document_id)
        async with self.client_factory() as s3:
            try:
                logger.debug(
                    'Uploading markdown to S3',
                    extra={
                        'collection': self.collection,
                        'key': key,
                        'document_id': document_id,
                    },
                )
                buf = BytesIO(md_text.encode('utf-8'))
                extra_args = {'ContentType': 'text/markdown; charset=utf-8'}

                await s3.upload_fileobj(buf, settings.aws_s3_bucket, key, ExtraArgs=extra_args)
                logger.success(
                    'Markdown uploaded to S3',
                    extra={'key': key, 'document_id': document_id},
                )
                return ArtifactInfo(
                    document_id=document_id,
                    collection=self.collection,
                    original_key=None,
                    markdown_key=key,
                )
            except Exception as e:
                logger.error(
                    'Failed to upload markdown to S3',
                    extra={'error': str(e), 'key': key, 'document_id': document_id},
                )
                raise

    async def delete(
        self,
        document_id: UUID,
        *,
        delete_original: bool = True,
        delete_markdown: bool = True,
    ) -> bool:
        """Delete artifacts for a document_id.

        This method lists objects under the document prefix and deletes keys that match
        requested targets. It is resilient to non-existent keys and returns True when
        there is nothing to delete.

        Args:
            document_id: Target document id whose artifacts should be removed.
            delete_original: Whether to delete the original file (any extension, with or without gzip).
            delete_markdown: Whether to delete the markdown copy.

        Returns:
            bool: True if deletion completed without client errors. False if a client error occurred.

        Notes:
            - Non-fatal errors log and return False rather than raising.
            - Original key detection is prefix-based and covers both `.ext` and `.ext.gz` variants.
        """
        prefix = self._prefix(document_id)
        targets: list[str] = []
        if delete_original:
            # We don't know extension or gzip beforehand; list and pick the original
            # Any key starting with prefix + 'original'
            targets.append('original')
        if delete_markdown:
            targets.append('document.md')

        async with self.client_factory() as s3:
            try:
                # List objects under prefix
                resp = await s3.list_objects_v2(Bucket=settings.aws_s3_bucket, Prefix=prefix)
                contents = resp.get('Contents', [])
                keys = [o['Key'] for o in contents]
                to_delete = []
                for k in keys:
                    if any(k.startswith(prefix + t) for t in targets):
                        to_delete.append({'Key': k})
                if not to_delete:
                    return True
                await s3.delete_objects(
                    Bucket=settings.aws_s3_bucket,
                    Delete={'Objects': to_delete, 'Quiet': True},
                )
                logger.success(
                    'Deleted S3 artifacts',
                    extra={'document_id': document_id, 'count': len(to_delete)},
                )
                return True
            except Exception as e:
                logger.error(
                    'Failed to delete S3 artifacts',
                    extra={'error': str(e), 'document_id': document_id},
                )
                return False

    async def load(self, key: str) -> bytes:
        """Load and return object bytes from S3 given a key.

        Args:
            key: Full S3 key to load (relative to the bucket root).

        Returns:
            bytes: Raw object bytes as stored (may be gzipped depending on key/encoding).

        Raises:
            Exception: Propagates underlying aioboto3/botocore exceptions when not found or inaccessible.
        """
        async with self.client_factory() as s3:
            try:
                resp = await s3.get_object(Bucket=settings.aws_s3_bucket, Key=key)
                body = await resp['Body'].read()
                return body
            except Exception as e:
                logger.error('Failed to load S3 object', extra={'error': str(e), 'key': key})
                raise

    async def head(self, key: str) -> FileInfo:
        """Return object metadata as FileInfo for a given key."""
        async with self.client_factory() as s3:
            resp = await s3.head_object(Bucket=settings.aws_s3_bucket, Key=key)
            last_modified = resp.get('LastModified')
            lm_iso = last_modified.isoformat() if hasattr(last_modified, 'isoformat') else None
            return FileInfo(
                key=key,
                size=resp.get('ContentLength') or 0,
                last_modified=lm_iso or '',
                content_type=resp.get('ContentType') or 'application/octet-stream',
                content_encoding=resp.get('ContentEncoding'),
                metadata=resp.get('Metadata', {}) or {},
            )

    def stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        """Async streaming iterator for an S3 object without buffering fully."""

        async def _gen() -> AsyncIterator[bytes]:
            async with self.client_factory() as s3:
                resp = await s3.get_object(Bucket=settings.aws_s3_bucket, Key=key)
                body = resp['Body']  # aioboto3 streaming body
                try:
                    while True:
                        chunk = await body.read(chunk_size)
                        if not chunk:
                            break
                        # pyright/mypy see this as bytes
                        yield chunk
                finally:
                    # close is sync; safe to call without await
                    with suppress(Exception):
                        body.close()

        return _gen()

    async def info(self, document_id: UUID) -> StoredFiles:
        """Return information about stored files for a document_id as StoredFiles.

        This lists objects under the document prefix and builds FileInfo entries using head().
        """
        prefix = self._prefix(document_id)
        async with self.client_factory() as s3:
            try:
                resp = await s3.list_objects_v2(Bucket=settings.aws_s3_bucket, Prefix=prefix)
                contents = resp.get('Contents', [])
                files: list[FileInfo] = []
                for o in contents:
                    key = o['Key']
                    # Prefer calling our own head() to ensure consistent shape
                    fi = await self.head(key)
                    # If size/last_modified missing from head (provider-dependent), fallback to list_objects values
                    if not fi.size:
                        try:
                            object.__setattr__(fi, 'size', o.get('Size') or 0)
                        except Exception:
                            pass
                    if not fi.last_modified:
                        lm = o.get('LastModified')
                        try:
                            object.__setattr__(
                                fi,
                                'last_modified',
                                lm.isoformat() if hasattr(lm, 'isoformat') else '',
                            )
                        except Exception:
                            pass
                    files.append(fi)
                return StoredFiles(
                    document_id=document_id,
                    collection=self.collection,
                    files=files,
                )
            except Exception as e:
                logger.error(
                    'Failed to get S3 info',
                    extra={'error': str(e), 'document_id': document_id},
                )
                raise
