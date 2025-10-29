from __future__ import annotations

from profiles.registry import DEFAULT_PROFILE_NAME, ProcessingProfileSettings
from profiles.registry import get_profile as _get_profile
from profiles.registry import iter_profiles as _iter_profiles


class ProfilesService:
    """Simple service wrapper exposing the profile registry."""

    def get(self, name: str = DEFAULT_PROFILE_NAME) -> ProcessingProfileSettings:
        return _get_profile(name)

    async def get_profiles(self) -> list[ProcessingProfileSettings]:
        return _iter_profiles()


# Convenience passthroughs for existing imports
get_profile = _get_profile
iter_profiles = _iter_profiles
