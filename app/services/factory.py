from app.core.config import get_settings
from app.core.profiles import ProcessingProfileSettings
from app.parsers.providers import parser_provider
from app.store.providers import default_store_provider
from app.vector.providers import default_ingestor_provider

from .document_service import DocumentService
from .job_service import JobService
from .profiles_service import ProfilesService, get_profile
from .upload_service import UploadService
from .upload_steps import UploadPipeline


def get_document_service() -> DocumentService:
    return DocumentService()


def get_job_service() -> JobService:
    return JobService()


def get_profile_settings(profile_name: str | None = None) -> ProcessingProfileSettings:
    if not profile_name:
        profile_name = get_settings().default_profile
    return get_profile(profile_name)


def get_upload_pipeline(profile: ProcessingProfileSettings) -> UploadPipeline:
    parser = parser_provider(name=profile.parser, config=profile.parser_config)
    store = default_store_provider(collection=profile.collection)
    ingestor = default_ingestor_provider(collection=profile.collection, config=profile.ingestor_config)

    return UploadPipeline(store=store, ingestor=ingestor, parser=parser)


def get_upload_service(profile_name: str | None = None) -> UploadService:
    if not profile_name:
        profile_name = get_settings().default_profile
    profile = get_profile_settings(profile_name)
    pipeline = get_upload_pipeline(profile=profile)
    return UploadService(collection=profile.collection, pipeline=pipeline)


def get_profiles_service() -> ProfilesService:
    return ProfilesService()
