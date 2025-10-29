import os
from pathlib import Path

import pytest
from fastapi import UploadFile

from api.file import TemporaryUploadFile


def test_saves_file_and_cleanup_deletes(tiny_pdf_upload: UploadFile):
    disk = TemporaryUploadFile.from_upload(tiny_pdf_upload)

    assert isinstance(disk.path, Path)
    assert disk.path.exists(), 'Expected temporary file to exist on disk'
    assert disk.path.suffix == '.pdf', 'Expected temporary file to have .pdf suffix'

    assert disk.filename == tiny_pdf_upload.filename
    assert disk.content_type == tiny_pdf_upload.content_type
    assert Path(disk.path).stat().st_size == tiny_pdf_upload.file.tell()
    assert disk.path.is_file()

    with open(disk.path, 'rb') as f:
        data = f.read()
    tiny_pdf_upload.file.seek(0)
    original = tiny_pdf_upload.file.read()
    assert data == original

    # Cleanup should delete the file
    disk.close()
    assert not os.path.exists(disk.path), 'Expected file to be deleted after cleanup()'

    # Cleanup again should be idempotent (no exception, still not exists)
    disk.close()
    assert not os.path.exists(disk.path)


@pytest.mark.asyncio
async def test_returns_hash(tiny_pdf_upload: UploadFile):
    disk = TemporaryUploadFile.from_upload(tiny_pdf_upload)
    digest = await disk.sha256_b64()
    assert len(digest) == 44
    assert digest == 'RBlR6lhUg1yxPHEZO2IkgR6vERxRrRPDU/DxxIwwL6c='


def test_has_size(tiny_pdf_upload: UploadFile):
    disk = TemporaryUploadFile.from_upload(tiny_pdf_upload)
    assert disk.size == tiny_pdf_upload.file.tell()
