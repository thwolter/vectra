from app.services.document_service import DocumentService
from app.services.job_service import JobService
from app.services.profiles_service import ProfilesService
from app.services.upload_service import UploadService


def get_document_service() -> DocumentService:
    return DocumentService()


def get_job_service() -> JobService:
    return JobService()


def get_upload_service() -> UploadService:
    return UploadService()


def get_profiles_service() -> ProfilesService:
    return ProfilesService()
