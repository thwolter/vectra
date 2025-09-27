from __future__ import annotations

from fastapi import APIRouter, Depends

from app.profiles.registry import ProcessingProfileSettings
from app.schemas.documents import ProfilesResponse
from app.services.factory import get_profiles_service
from app.services.profiles_service import ProfilesService

router = APIRouter(prefix='/v1/profiles')


@router.get('/', response_model=ProfilesResponse, tags=['profiles'])
async def get_profiles(
    profiles_service: ProfilesService = Depends(get_profiles_service),
) -> list[ProcessingProfileSettings]:
    """List available processing profiles and their capabilities."""
    return await profiles_service.get_profiles()
