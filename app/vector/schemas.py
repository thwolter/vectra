from __future__ import annotations


from pydantic import BaseModel, Field

from app.utils.types import SHA256B64


class IngestionVersionKey(BaseModel):
    """Schema representing the unique key of an ingestion version.

    Uniqueness is defined by the tuple:
    (collection, source, content_fp, chunker_version, embed_model, embed_model_ver)
    """

    collection: str = Field(..., description='Vector collection name')
    digest: SHA256B64
    chunker_version: str = Field(..., description='Semantic chunker version identifier')
    embed_model: str = Field(..., description='Embedding model name')
    embed_model_ver: str = Field(..., description='Embedding model version')


class IngestionVersionInsert(IngestionVersionKey):
    """Schema for inserting an ingestion version.

    Extends the unique key with the deterministic document id used elsewhere
    in the pipeline. Note: The current table schema does not persist digest;
    it is kept here for interface symmetry and potential future use.
    """

    pass


class IngestionResult(BaseModel):
    digest: SHA256B64
    collection: str
    total_docs: int
    batches: int
    skipped: bool = False
    reason: str | None = None
