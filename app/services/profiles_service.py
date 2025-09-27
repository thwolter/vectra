from __future__ import annotations

from typing import Dict

from app.core.profiles import ProcessingProfileSettings
from app.parsers.docling import DoclingParserConfig
from app.vector.models import IngestorSettings

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


class ProfilesService:
    """Simple service wrapper exposing the profile registry."""

    def get(self, name: str = DEFAULT_PROFILE_NAME) -> ProcessingProfileSettings:
        return get_profile(name)

    async def get_profiles(self) -> list[ProcessingProfileSettings]:
        return iter_profiles()


# Register the in-process default profile immediately so consumers always have one.
register_profile(
    ProcessingProfileSettings(
        name=DEFAULT_PROFILE_NAME,
        ingestor_config=IngestorSettings(),
        parser_config=DoclingParserConfig(),
    )
)
