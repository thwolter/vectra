from app.parsers.providers import parser_provider
from app.schemas.enums import CollectionEnum
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


def get_upload_pipeline(collection: CollectionEnum) -> UploadPipeline:
    store = default_store_provider(collection=collection)
    ingestor = default_ingestor_provider(collection=collection)
    parser = parser_provider(profile='docling')
    return UploadPipeline(store=store, ingestor=ingestor, parser=parser)


def get_upload_service() -> UploadService:
    collection = CollectionEnum.DEFAULT
    pipeline = get_upload_pipeline(collection=collection)
    return UploadService(collection=collection, pipeline=pipeline)


def get_profiles_service() -> ProfilesService:
    return ProfilesService()
