from functools import lru_cache
from typing import List, Literal

from nexor.config.settings import ServiceSettings
from nexor.utils import get_app_version, get_app_name
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from core.utils import FingerprintMixin

from .utils import ValidatedModel


class AllowedUploadFiles(ValidatedModel):
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


class LlamaCloudSettings(ValidatedModel, FingerprintMixin):
    required_keys = ['api_key']
    fingerprint_exclude = ['api_key']

    api_key: SecretStr | None = None
    parse_mode: str = 'parse_page_with_agent'
    high_res_ocr: bool = True
    adaptive_long_table: bool = True
    outlined_table_extraction: bool = True
    output_tables_as_HTML: bool = True
    model: str = 'openai-gpt-5-mini'
    extract_layout: bool = True
    continuous_mode: bool = True


class TextSplitterSettings(ValidatedModel, FingerprintMixin):
    chunker: str = 'MarkdownHeaderTextSplitter'
    version: str = '1'
    min_heading_level: int = 1
    max_heading_level: int = 6


class EmbeddingSettings(ValidatedModel, FingerprintMixin):
    fingerprint_exclude = ['max_tokens_per_request', 'max_docs_per_batch']

    version: str = '1'
    collection: str = 'default'
    model: str = 'text-embedding-3-small'
    dim: int = 1536
    max_tokens_per_request: int = 300000
    max_docs_per_batch: int = 100


class AWSSettings(ValidatedModel):
    required_keys = ['access_key_id', 'secret_access_key']
    access_key_id: SecretStr | None = None
    secret_access_key: SecretStr | None = None
    region: str = 'eu-west-1'
    s3_bucket: str = 'vecapi-documents'
    s3_path: str = 'documents'


class Settings(ServiceSettings):
    required_keys = ServiceSettings.required_keys + ['redis_url', 'openai_api_key', 'dramatiq_broker_url']

    model_config = SettingsConfigDict(
        env_file='.env',  # let pydantic-settings read .env
        case_sensitive=False,  # typical for envs
        extra='ignore',  # ignore unknown env vars
        env_nested_delimiter='__',
    )

    app_schema: str = 'vectra'

    env: Literal['development', 'production', 'testing'] = 'production'
    app_name: str = Field(default_factory=get_app_name)
    debug: bool | None = True
    version: str = Field(default_factory=get_app_version)
    admin_email: str = 'support@riskary.de'

    default_profile: str = 'default'
    default_parser: Literal['docling', 'llama', 'test'] = 'llama'

    redis_url: SecretStr | None = None

    # ChatDoc API configuration
    chatdoc_api_key: SecretStr | None = None
    chatdoc_api_url: str = 'https://api.chatdoc.com'

    # Parser and Text splitter configuration
    llama_cloud: LlamaCloudSettings = LlamaCloudSettings()
    text_splitter: TextSplitterSettings = TextSplitterSettings()

    allowed_upload_files: AllowedUploadFiles = AllowedUploadFiles()
    embedding: EmbeddingSettings = EmbeddingSettings()

    # OpenAI API configuration for embeddings
    openai_api_key: SecretStr | None = None

    document_store: Literal['local', 's3'] = 's3'
    local_file_path: str = '../documents'

    # AWS S3 configuration
    aws: AWSSettings = AWSSettings()

    # JWT configuration
    jwt_secret: SecretStr = SecretStr('dev-secret-change-me')
    jwt_issuer: str = 'vecapi'
    jwt_audience: str = 'vecapi-clients'
    jwt_ttl_seconds: int = 3600

    # Dramatiq task processing
    dramatiq_broker_url: SecretStr | None = None
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


# @lru_cache
def get_settings() -> Settings:
    return Settings()
