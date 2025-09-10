from __future__ import annotations

from app.schemas.documents import ProfilesResponse


class ProfilesService:
    """Service to expose available parser/embedding profiles to clients."""

    async def get_profiles(self) -> ProfilesResponse:
        # :todo read from registry (DB/YAML) and return
        raise NotImplementedError
