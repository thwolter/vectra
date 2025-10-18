import json
from functools import lru_cache
from typing import Any, Iterable, Literal, Annotated

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings

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
    cors_allow_origins: tuple[str] = []

    @field_validator('cors_allow_origins', mode='before')
    @classmethod
    def normalize_cors_origins(cls, value: Any) -> tuple[str, ...]:
        """Normalize configured origins so they match browser preflight requests."""
        if not value:
            return ()

        raw_value: Any = value
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
            if not raw_value:
                return ()
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError:
                parsed = [part.strip() for part in raw_value.split(',') if part.strip()]
            else:
                match parsed:
                    case str() as single:
                        parsed = [single]
                    case list() | tuple() | set():
                        parsed = list(parsed)
                    case _:
                        parsed = [str(parsed)]
            raw_value = parsed
        elif isinstance(raw_value, (set, tuple)):
            raw_value = list(raw_value)
        elif not isinstance(raw_value, list):
            raw_value = [str(raw_value)]

        normalized: list[str] = []
        for origin in raw_value:
            origin_str = str(origin).strip()
            if not origin_str:
                continue
            normalized.append(origin_str.rstrip('/'))
        return tuple(normalized)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

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


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return settings
