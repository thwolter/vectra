import json
import os
import pathlib
import tomllib
import warnings
from functools import lru_cache
from typing import ClassVar

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings


@lru_cache(maxsize=1)
def load_version() -> str:
    try:
        path = pathlib.Path(__file__).resolve().parents[2] / 'pyproject.toml'
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        return data['project']['version']
    except FileNotFoundError:
        return 'unknown'


def parse_cors_origins(value: str | list[str] | None) -> tuple[str, ...]:
    if not value:
        return ()
    if value in ('*', '"*"'):
        return ('*',)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                return (parsed.strip().rstrip('/'),)
            if isinstance(parsed, (list, tuple)):
                return tuple(o.strip().rstrip('/') for o in parsed)
        except json.JSONDecodeError:
            return tuple(o.strip().rstrip('/') for o in value.split(',') if o.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(o).strip().rstrip('/') for o in value)
    return (str(value).strip().rstrip('/'),)


def _check_missing_keys(s: BaseSettings | BaseModel, *, sub_key='') -> list[str]:
    env = os.getenv('ENV', '').lower()
    testing_mode = env.startswith('testing')
    missing = []

    for key in getattr(s, 'required_keys', []):
        value = getattr(s, key, None)
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if not value or not str(value).strip():
            if sub_key:
                name = f'{sub_key.upper()}__{key.upper()}'
            else:
                name = f'{key.upper()}'
            missing.append(name)

    # recurse into nested settings
    for field_key, field_value in s.__dict__.items():
        if isinstance(field_value, (ValidatedSettings, ValidatedModel)):
            missing += _check_missing_keys(field_value, sub_key=field_key)

    if missing and not sub_key:
        message = f'Missing required environment keys: {", ".join(missing)}'
        if testing_mode:
            warnings.warn(message)
        else:
            raise RuntimeError(message)

    return missing


class ValidatedSettings(BaseSettings):
    """Base class with reusable validation logic."""

    required_keys: ClassVar[list[str]] = []

    def check_missing_keys(self) -> list[str]:
        return _check_missing_keys(self)


class ValidatedModel(BaseModel):
    """Base class with reusable validation logic."""

    required_keys: ClassVar[list[str]] = []

    def check_missing_keys(self) -> list[str]:
        return _check_missing_keys(self)
