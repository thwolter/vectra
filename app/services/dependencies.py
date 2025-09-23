from app.core.profiles import ProcessingProfileSettings
from app.parsers.providers import parser_provider
from app.store.providers import default_store_provider
from app.vector.providers import default_ingestor_provider

from .document_service import DocumentService
from .job_service import JobService
from .profiles_service import ProfilesService
from .upload_service import UploadService
from .upload_steps import UploadPipeline


def get_document_service() -> DocumentService:
    return DocumentService()


def get_job_service() -> JobService:
    return JobService()


def get_profile_settings(profile_name: str = 'default') -> ProcessingProfileSettings:
    profile_service = ProfilesService()
    return profile_service.get(profile_name)


def get_upload_pipeline(profile: ProcessingProfileSettings) -> UploadPipeline:
    parser = parser_provider(name=profile.parser, config=profile.parser_config)
    store = default_store_provider(collection=profile.collection)
    ingestor = default_ingestor_provider(collection=profile.collection, config=profile.ingestor_config)

    return UploadPipeline(store=store, ingestor=ingestor, parser=parser)


def get_upload_service(profile_name: str = 'default') -> UploadService:
    profile = get_profile_settings(profile_name)
    pipeline = get_upload_pipeline(profile=profile)
    return UploadService(collection=profile.collection, pipeline=pipeline)


def get_profiles_service() -> ProfilesService:
    return ProfilesService()
