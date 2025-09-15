import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Generator

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers


@pytest.fixture
def apple_report_first_page() -> str:
    """Path to the first page of the Apple 10-Q test PDF under tests/data.

    Returns the absolute filesystem path as a string.
    """
    return str(Path(__file__).parents[1] / 'data' / '10-Q4-2024-As-Filed Seite 1.pdf')


@pytest.fixture
def tiny_pdf() -> str:
    """Path to a tiny test PDF under tests/data."""
    return str(Path(__file__).parents[1] / 'data' / 'tiny.pdf')


@pytest.fixture
def small_pdf() -> str:
    """Path to a small test PDF under tests/data."""
    return str(Path(__file__).parents[1] / 'data' / 'small.pdf')


@pytest.fixture
def pdf_bytes_tiny() -> bytes:
    """Minimal valid-ish PDF bytes for tests."""
    return b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n%%EOF\n'


@pytest.fixture
def upload_file_factory(
    tmp_path: Path,
) -> Generator[Callable[[bytes, str, str], UploadFile], Any, None]:
    """Factory yielding a callable to create UploadFile objects backed by temp files.

    The factory tracks created temp files and cleans them up after the test.
    Usage:
        def test_something(upload_file_factory, pdf_bytes_tiny):
            f = upload_file_factory(pdf_bytes_tiny, 'tiny.pdf', 'application/pdf')
    """
    opened_files: list[Any] = []
    tmp_files: list[Path] = []

    def _make(content: bytes, filename: str, content_type: str) -> UploadFile:
        tmp = tempfile.NamedTemporaryFile(
            delete=False, dir=tmp_path, suffix=Path(filename).suffix or ''
        )
        tmp.write(content)
        tmp.flush()
        tmp.close()
        tmp_files.append(Path(tmp.name))
        f = open(tmp.name, 'rb')
        opened_files.append(f)
        headers = Headers({'content-type': content_type})
        return UploadFile(filename=filename, file=f, headers=headers)

    try:
        yield _make
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass
        for p in tmp_files:
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass


@pytest.fixture
def tiny_pdf_upload(
    upload_file_factory, pdf_bytes_tiny
) -> Generator[UploadFile, Any, None]:
    """Backwards-compatible UploadFile fixture using the generic factory."""
    upload = upload_file_factory(pdf_bytes_tiny, 'tiny.pdf', 'application/pdf')
    try:
        yield upload
    finally:
        # Cleanup is handled by upload_file_factory finalizer
        pass


@pytest.fixture
def apple_report_first_page_upload(
    apple_report_first_page: str,
) -> Generator[UploadFile, Any, None]:
    """Create an UploadFile from the Apple report first-page test PDF.

    Ensures correct content-type header and proper file handle cleanup.
    """
    f = open(apple_report_first_page, 'rb')
    try:
        headers = Headers({'content-type': 'application/pdf'})
        upload = UploadFile(
            filename=Path(apple_report_first_page).name, file=f, headers=headers
        )
        yield upload
    finally:
        try:
            f.close()
        except Exception:
            pass
