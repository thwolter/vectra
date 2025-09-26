from functools import lru_cache
from typing import Literal, Any

from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    env: Literal['development', 'production', 'testing'] = 'development'
    app_name: str = 'FastAPI'
    debug: bool = True
    version: str = '0.1.0'
    admin_email: str = 'support@riskary.de'

    default_profile: str = 'default'

    postgres_url: SecretStr
    redis_url: SecretStr

    # ChatDoc API configuration
    chatdoc_api_key: SecretStr
    chatdoc_api_url: str = 'https://api.chatdoc.com'

    # OpenAI API configuration for embeddings
    openai_api_key: SecretStr

    document_store: Literal['local', 's3'] = 's3'
    local_file_path: str = 'documents'

    # AWS S3 configuration
    aws_access_key_id: SecretStr
    aws_secret_access_key: SecretStr
    aws_region: str = 'eu-west-1'
    aws_s3_bucket: str = 'vecapi-documents'
    aws_s3_path: str = 'documents' if env == 'production' else 'documents-dev'

    # JWT configuration
    jwt_secret: SecretStr = SecretStr('dev-secret-change-me')
    jwt_issuer: str = 'vecapi'
    jwt_audience: str = 'vecapi-clients'
    jwt_ttl_seconds: int = 3600

    # Dramatiq task processing
    dramatiq_broker_url: SecretStr
    dramatiq_queue_name: str = 'upload-processing'
    dramatiq_time_limit_ms: int = 15 * 60 * 1000
    dramatiq_max_retries: int = 3

    # Monitoring & alerting
    monitoring_enabled: bool = True
    metrics_endpoint_enabled: bool = True
    alerting_webhook_url: SecretStr | None = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    @property
    def pg_vector_url(self) -> SecretStr:
        """
        Returns the PostgreSQL database URL for PGVector.
        Converts 'postgres://' to 'postgresql://' if needed.
        """
        url = self.postgres_url.get_secret_value()
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        if self.env != 'production':
            # replace the database postgres by test
            # use hte last occurrence of /postgres
            url = url.rsplit('/', 1)[0] + '/test'
        return SecretStr(url)


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return settings
