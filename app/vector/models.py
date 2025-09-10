from __future__ import annotations

from pydantic_settings import BaseSettings


class IngestorSettings(BaseSettings):
    """Configuration for ingestion limits and embedding model.

    - model_name: name of embedding model used by the vector
    - embed_model_ver: semantic version or hash for model settings
    - chunker_version: semantic version of chunking logic
    - max_tokens_per_request: hard cap for total tokens per batch
    - max_docs_per_batch: hard cap for number of docs per batch
    """

    model_name: str = 'text-embedding-3-small'
    embed_model_ver: str = 'v1'
    chunker_version: str = 'v1'
    max_tokens_per_request: int = 300000
    max_docs_per_batch: int = 100
