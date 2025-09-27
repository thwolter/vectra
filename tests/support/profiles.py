from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np
from langchain_core.embeddings import Embeddings

from app.core.profiles import ProcessingProfileSettings
from app.parsers.protocols import ParserProtocol
from app.parsers.providers import register_parser_provider
from app.parsers.schemas import ParserConfig
from app.services.profiles_service import register_profile
from app.vector.factory import register_embeddings_provider
from app.vector.models import IngestorSettings
from tests.support.fakes import FakeSampleParser


class TestEmbeddings(Embeddings):
    """Deterministic embeddings implementation for test pipelines."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def _vector_for(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:16], 16) % (2**32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dim)
        vec /= np.linalg.norm(vec) + 1e-12
        return vec.astype(np.float32).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)


class TestParserConfig(ParserConfig):
    sample_path: Path = Path(__file__).resolve().parents[1] / 'data' / 'sample_docs.pkl'


def _test_parser_factory(*, config: ParserConfig) -> ParserProtocol:
    if not isinstance(config, TestParserConfig):
        config = TestParserConfig(**config.model_dump())
    return FakeSampleParser(sample_path=Path(config.sample_path))


register_parser_provider('test', _test_parser_factory)
register_embeddings_provider('test', lambda config: TestEmbeddings(dim=config.embed_dim))


def build_test_profile(
    *,
    name: str = 'test',
    collection: str = 'default',
    sample_path: Optional[Path] = None,
) -> ProcessingProfileSettings:
    parser_config = TestParserConfig()
    if sample_path is not None:
        parser_config = TestParserConfig(sample_path=sample_path)

    return ProcessingProfileSettings(
        name=name,
        collection=collection,
        parser='test',
        parser_config=parser_config,
        ingestor_config=IngestorSettings(embedding_provider='test'),
    )


TestProcessingProfile = build_test_profile()
register_profile(TestProcessingProfile)


def ensure_test_profile(sample_path: Optional[Path] = None) -> ProcessingProfileSettings:
    """Register the canonical test profile, optionally overriding the sample path."""

    profile = TestProcessingProfile
    if sample_path is not None:
        profile = build_test_profile(sample_path=sample_path)
    register_profile(profile)
    return profile
