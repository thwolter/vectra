from functools import lru_cache
from typing import Any, List, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils import load_version, parse_cors_origins


class AllowedUploadFiles(BaseModel):
    allowed_extensions: list[str] = ['pdf', 'docx', 'doc', 'txt', 'html', 'htm', 'md', 'rst', 'json', 'yaml', 'yml']
    upload_size_limit: int = 100 * 1024 * 1024
    content_type: List[str] = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
        'text/html',
        'text/markdown',
        'text/x-rst',
        'application/json',
        'application/x-yaml',
        'text/yaml',
    ]


class LlamaCloudSettings(BaseModel):
    api_key: SecretStr | None = None
    parse_mode: str = 'parse_page_with_agent'
    high_res_ocr: bool = True
    adaptive_long_table: bool = True
    outlined_table_extraction: bool = True
    output_tables_as_HTML: bool = True
    model: str = 'openai-gpt-5-mini'

    @field_validator('api_key')
    @classmethod
    def require_api_key_in_prod(cls, v):
        import os

        if os.getenv('ENV') == 'prod' and v is None:
            raise ValueError('LLAMA_CLOUD__API_KEY required in production')
        return v


class TextSplitterSettings(BaseModel):
    min_heading_level: int = 1
    max_heading_level: int = 6


class EmbeddingSettings(BaseModel):
    version: str = '1'
    collection: str = 'default'
    model: str = 'text-embedding-3-small'
    dim: int = 1536
    max_tokens_per_request: int = 300000
    max_docs_per_batch: int = 100


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='__')

    env: Literal['development', 'production', 'testing'] = 'production'
    app_name: str = 'Vectra'
    debug: bool = True
    version: str = Field(default_factory=load_version)
    admin_email: str = 'support@riskary.de'

    default_profile: str = 'default'
    default_parser: Literal['docling', 'llama', 'test'] = 'llama'

    postgres_url: SecretStr
    redis_url: SecretStr
    db_schema: str = 'vectra'

    # ChatDoc API configuration
    chatdoc_api_key: SecretStr | None = None
    chatdoc_api_url: str = 'https://api.chatdoc.com'

    # Parser and Text splitter configuration
    llama_cloud: LlamaCloudSettings = LlamaCloudSettings()  # type: ignore[assignment]
    text_splitter: TextSplitterSettings = TextSplitterSettings()

    allowed_upload_files: AllowedUploadFiles = AllowedUploadFiles()
    embedding: EmbeddingSettings = EmbeddingSettings()

    # OpenAI API configuration for embeddings
    openai_api_key: SecretStr

    document_store: Literal['local', 's3'] = 's3'
    local_file_path: str = '../documents'

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
    service_name_app: str = 'src'
    service_name_worker: str = 'worker'

    cors_allow_origins: tuple[str, ...] = ()

    @field_validator('cors_allow_origins', mode='before')
    @classmethod
    def _normalize_cors_origins(cls, value: Any) -> tuple[str, ...]:
        return parse_cors_origins(value)

    @field_validator('postgres_url', mode='before')
    @classmethod
    def _normalise_postgres_url(cls, url) -> SecretStr:
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return SecretStr(url)

    @property
    def async_postgres_url(self) -> SecretStr:
        dsn = self.postgres_url.get_secret_value()
        if dsn.startswith('postgresql://'):
            dsn = dsn.replace('postgresql://', 'postgresql+asyncpg://', 1)
        if dsn.startswith('postgres://'):
            dsn = dsn.replace('postgres://', 'postgresql+asyncpg://', 1)
        return SecretStr(dsn)


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings()  # type: ignore[missing-argument]
