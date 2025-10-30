import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.utils import check_file_type_size
from core.config import get_settings


async def test_check_file_type_size_allows_supported_type():
    file = SimpleNamespace(content_type='application/pdf', file=io.BytesIO(b'abc'))
    await check_file_type_size(file)


async def test_check_file_type_size_rejects_unsupported_type():
    get_settings.cache_clear()
    settings = get_settings()
    settings.allowed_upload_files.content_type = ['application/pdf']
    file = SimpleNamespace(content_type='image/png', file=io.BytesIO(b'abc'))

    with pytest.raises(HTTPException) as exc:
        await check_file_type_size(file)
    assert exc.value.status_code == 415


async def test_check_file_type_size_rejects_large_files():
    get_settings.cache_clear()
    settings = get_settings()
    settings.allowed_upload_files.upload_size_limit = 1
    file = SimpleNamespace(content_type='application/pdf', file=io.BytesIO(b'abcde'))

    with pytest.raises(HTTPException) as exc:
        await check_file_type_size(file)
    assert exc.value.status_code == 413
