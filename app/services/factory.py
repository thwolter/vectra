from app.schemas.enums import CollectionEnum
from app.services.document_service import DocumentService
from app.services.profiles_service import ProfilesService
from app.services.upload_service import UploadService
from app.services.job_service import JobService


def get_company_document_service():
    return DocumentService(collection=CollectionEnum.FINANCIAL)


def get_default_document_service():
    return DocumentService(collection=CollectionEnum.DEFAULT)


def get_document_service() -> DocumentService:
    # default document service for API; can be overridden in tests
    return DocumentService(collection=CollectionEnum.DEFAULT)


def get_job_service() -> JobService:
    return JobService()


def get_upload_service() -> UploadService:
    collection = CollectionEnum.DEFAULT
    return UploadService(collection=collection)


def get_profiles_service() -> ProfilesService:
    return ProfilesService()
