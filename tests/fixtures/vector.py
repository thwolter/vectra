from __future__ import annotations

import hashlib
from typing import Callable, List

import numpy as np
import pytest
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from vector.factory import get_vectorstore
from vector.models import IngestorSettings


class FakeEmbeddings(Embeddings):
    """Deterministic, fast embeddings for tests.

    Generates L2-normalized vectors using a hash-seeded RNG so the same input
    text yields the same vector across runs and processes.
    """

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def _vec_for(self, text: str) -> list[float]:
        # Stable seed per text
        seed = int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:16], 16) % (2**32)
        rng = np.random.default_rng(seed)
        # Draw from N(0,1) then L2-normalize for dot/cosine stability
        v = rng.standard_normal(self.dim)
        v /= np.linalg.norm(v) + 1e-12
        return v.astype(np.float32).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:  # sync OK for tests
        return [self._vec_for(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._vec_for(text)


# Factory-style fixtures to avoid shared state between tests and processes
@pytest.fixture
def fake_embeddings() -> Callable[[int], Embeddings]:
    """Factory for FakeEmbeddings with configurable dimension.

    Usage:
        emb = fake_embeddings(256)
    """

    def _make(dim: int = 1536) -> Embeddings:
        return FakeEmbeddings(dim=dim)

    return _make


@pytest.fixture
def vectorstore_factory(session) -> Callable[[str, Embeddings | None], PGVector]:
    """Factory returning a PGVector for the given collection bound to test tenant.

    Prefer this over a single shared instance to ensure isolation and
    parallel-safety when using pytest-xdist.
    """

    tenant_id = session.info['tenant_id']

    def _make(collection: str, embeddings: Embeddings | None = None) -> PGVector:
        return get_vectorstore(
            collection=collection,
            tenant_id=tenant_id,
            embeddings=embeddings or FakeEmbeddings(),
            config=IngestorSettings(embedding_provider='test'),
        )

    return _make
