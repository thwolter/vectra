from __future__ import annotations

from pydantic import BaseModel


class IngestorSettings(BaseModel):
    chunker_model: str = 'docling'
    chunker_version: str = 'v1'
    chunker_params: dict = {}

    embedding_provider: str = 'openai'
    embed_model: str = 'text-embedding-3-small'
    embed_model_version: str = 'v1'
    embed_dim: int = 1536

    max_tokens_per_request: int = 300000
    max_docs_per_batch: int = 100
