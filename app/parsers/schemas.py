from typing import List

from langchain_core.documents import Document
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ParserConfig(BaseSettings):
    """Base configuration for document parsers."""

    # Common configuration options for all parsers
    cache_results: bool = True
    model_name: str = 'gpt-4'
    max_tokens: int = 128 * 1024


class ParseResult(BaseModel):
    """Base class for parser results."""

    documents: List[Document] = Field(default_factory=list)
