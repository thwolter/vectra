from __future__ import annotations

from typing import Dict

from pydantic import BaseModel

from app.core.config import get_settings
from app.parsers.schemas import ParserConfig
from app.vector.models import IngestorSettings


class ProcessingProfileSettings(BaseModel):
    name: str = 'default'
    collection: str = 'default'

    max_upload_size: int = 50 * 1024 * 1024  # 50 MB
    allowed_upload_types: set[str] = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
        'application/msword',  # legacy .doc
        'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx (if supported)
    }

    ingestor_config: IngestorSettings = IngestorSettings()

    parser: str = 'llama'
    parser_config: ParserConfig = ParserConfig()


PROFILE_REGISTRY: Dict[str, ProcessingProfileSettings] = {}
DEFAULT_PROFILE_NAME = 'default'


def register_profile(profile: ProcessingProfileSettings) -> None:
    """Register or replace a processing profile configuration."""
    PROFILE_REGISTRY[profile.name] = profile


def get_profile(name: str = DEFAULT_PROFILE_NAME) -> ProcessingProfileSettings:
    """Return the requested profile, falling back to the default profile."""
    if name in PROFILE_REGISTRY:
        return PROFILE_REGISTRY[name]
    if DEFAULT_PROFILE_NAME in PROFILE_REGISTRY:
        return PROFILE_REGISTRY[DEFAULT_PROFILE_NAME]
    raise KeyError(f'Profile {name!r} not found and no default profile registered.')


def iter_profiles() -> list[ProcessingProfileSettings]:
    """Return a snapshot list of all registered profiles."""
    return list(PROFILE_REGISTRY.values())


# Register the in-process default profile immediately so consumers always have one.
register_profile(
    ProcessingProfileSettings(
        name=DEFAULT_PROFILE_NAME,
        parser=get_settings().default_parser,
        ingestor_config=IngestorSettings(),
        parser_config=ParserConfig(),
    )
)
