from core.config import get_settings
from store.providers import default_store_provider

from .document_service import DocumentService
from .job_service import JobService
from .retrieval_service import RetrievalService
from .upload_service import UploadService
from .upload_steps import UploadPipeline


def get_document_service() -> DocumentService:
    return DocumentService()


def get_job_service() -> JobService:
    return JobService()


def get_upload_service() -> UploadService:
    settings = get_settings()
    collection = settings.embedding.collection
    store = default_store_provider(collection=collection)
    pipeline = UploadPipeline(store=store)
    return UploadService(collection=collection, pipeline=pipeline)


def get_retrieval_service() -> RetrievalService:
    return RetrievalService()
