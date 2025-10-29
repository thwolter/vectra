from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DocumentContent(BaseModel):
    """Content of a document."""

    content: str = Field(..., description='Text content of the document')
    metadata: dict = Field(..., description='Metadata of the document')


class DocumentChunk(BaseModel):
    """A chunk of a document with its metadata."""

    content: str = Field(..., description='Text content of the chunk')
    metadata: Dict[str, Any] = Field(..., description='Metadata of the chunk')
    chunk_id: str = Field(..., description='Unique identifier for the chunk')
    chunk_index: int = Field(..., description='Index of the chunk in the document')


class ProcessedDocument(BaseModel):
    """A processed document with its chunks."""

    original_content: DocumentContent = Field(..., description='Original content of the document')
    chunks: List[DocumentChunk] = Field(..., description='Chunks of the document')
    total_chunks: int = Field(..., description='Total number of chunks')
