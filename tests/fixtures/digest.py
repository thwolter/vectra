from __future__ import annotations

import base64
import hashlib
import os
from typing import Callable

import pytest
from app.utils.types import SHA256B64


@pytest.fixture
def digest_random() -> SHA256B64:
    """Return a random SHA256 digest (base64) each time it's requested."""
    return base64.b64encode(os.urandom(32)).decode('ascii')


@pytest.fixture
def digest_zero() -> SHA256B64:
    """Return a constant, known digest. Uses SHA256("") in base64."""
    return base64.b64encode(hashlib.sha256(b'').digest()).decode('ascii')


@pytest.fixture
def digest_from() -> Callable[[str], SHA256B64]:
    """Factory fixture producing deterministic base64 sha256 digests from text.

    Usage in tests:
        def test_something(digest_from):
            d1 = digest_from("foo")
            d2 = digest_from("bar")
    """

    def _make(text: str) -> SHA256B64:
        return base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode(
            'ascii'
        )

    return _make
