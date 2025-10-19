from functools import lru_cache
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings

from .helper import parse_cors_origins

load_dotenv()


class Settings(BaseSettings):
    env: Literal['development', 'production', 'testing'] = 'production'
    app_name: str = 'Vetra'
    debug: bool = True
    version: str = '0.2.0'
    admin_email: str = 'support@riskary.de'

    default_profile: str = 'default'
    default_parser: Literal['docling', 'llama', 'test'] = 'docling'

    postgres_url: SecretStr
    redis_url: SecretStr

    # ChatDoc API configuration
    chatdoc_api_key: SecretStr | None = None
    chatdoc_api_url: str = 'https://api.chatdoc.com'

    # Llama Cloud
    llama_cloud_api_key: SecretStr | None = None

    # OpenAI API configuration for embeddings
    openai_api_key: SecretStr

    document_store: Literal['local', 's3'] = 's3'
    local_file_path: str = '/documents'

    # AWS S3 configuration
    aws_access_key_id: SecretStr
    aws_secret_access_key: SecretStr
    aws_region: str = 'eu-west-1'
    aws_s3_bucket: str = 'vecapi-documents'
    aws_s3_path: str = 'documents'

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

    worker_heartbeat_ttl: int = 30
    worker_heartbeat_interval: int = 10

    # Logging configuration
    log_level: str = 'WARNING'  # e.g., DEBUG, INFO, WARNING, ERROR
    # Console should be plain text; OTEL can receive structured JSON
    log_console_plain: bool = True
    log_enqueue: bool = True
    log_backtrace: bool = True
    log_diagnose: bool = False
    log_remove_default_sink: bool = True

    # --- OpenTelemetry / Observability ---
    otel_enabled: bool = True
    otel_logs_exporter: str = 'otlp'
    log_otel_json: bool = True
    service_namespace: str = 'finrag'
    deployment_env: str = 'development'
    service_name_app: str = 'app'
    service_name_worker: str = 'worker'
    cors_allow_origins: tuple[str, ...] = ()

    @field_validator('cors_allow_origins', mode='before')
    @classmethod
    def normalize_cors_origins(cls, value: Any) -> tuple[str, ...]:
        return parse_cors_origins(value)

    @property
    def pg_vector_url(self) -> SecretStr:
        """
        Returns the PostgreSQL database URL for PGVector.
        Converts 'postgres://' to 'postgresql://' if needed.
        Also trims accidental surrounding whitespace that could lead to
        invalid database names like "test ".
        """
        url = self.postgres_url.get_secret_value().strip()
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return SecretStr(url)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[missing-argument]
