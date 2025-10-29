import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.utils import check_file_type_size
from profiles.registry import ProcessingProfileSettings


@pytest.mark.asyncio
async def test_check_file_type_size_allows_supported_type():
    config = ProcessingProfileSettings()
    file = SimpleNamespace(content_type='application/pdf', file=io.BytesIO(b'abc'))

    await check_file_type_size(file, config=config)


@pytest.mark.asyncio
async def test_check_file_type_size_rejects_unsupported_type():
    config = ProcessingProfileSettings()
    file = SimpleNamespace(content_type='image/png', file=io.BytesIO(b'abc'))

    with pytest.raises(HTTPException) as exc:
        await check_file_type_size(file, config=config)
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_check_file_type_size_rejects_large_files():
    config = ProcessingProfileSettings(max_upload_size=2)
    file = SimpleNamespace(content_type='application/pdf', file=io.BytesIO(b'abcde'))

    with pytest.raises(HTTPException) as exc:
        await check_file_type_size(file, config=config)
    assert exc.value.status_code == 413
