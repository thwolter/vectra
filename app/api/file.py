import base64
import hashlib
import os
import shutil
from tempfile import NamedTemporaryFile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fastapi import UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.utils.types import SHA256B64

_CHUNK_SIZE: Final[int] = 1024 * 1024  # 1 MB


@dataclass
class TemporaryUploadFile:
    path: Path
    filename: str
    content_type: str

    @classmethod
    def from_upload(cls, file: UploadFile) -> 'TemporaryUploadFile':
        if not (isinstance(file, UploadFile) or isinstance(file, StarletteUploadFile)):
            raise ValueError(f'Expected UploadFile, got {type(file)}')

        if not file.filename:
            raise ValueError('Missing filename')

        if not file.content_type:
            raise ValueError('Missing content_type')

        with NamedTemporaryFile(
            delete=False, suffix=Path(file.filename or '').suffix
        ) as tmp:
            file.file.seek(0)
            shutil.copyfileobj(file.file, tmp)  # type: ignore[assignment]
            path = Path(tmp.name)
        return TemporaryUploadFile(
            path=path, filename=file.filename, content_type=file.content_type
        )

    def close(self) -> None:
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    async def sha256_b64(self) -> SHA256B64:
        with open(self.path, 'rb') as f:
            f.seek(0)
            h = hashlib.sha256()
            while chunk := f.read(_CHUNK_SIZE):
                h.update(chunk)

            return base64.b64encode(h.digest()).decode('ascii')
