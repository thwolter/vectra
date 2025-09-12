import base64
import os

from app.utils.types import SHA256B64
import pytest


@pytest.fixture
def random_digest() -> 'SHA256B64':
    return base64.b64encode(os.urandom(32)).decode('ascii')


@pytest.fixture
def another_random_digest() -> 'SHA256B64':
    return base64.b64encode(os.urandom(32)).decode('ascii')


@pytest.fixture
def digest_str() -> 'SHA256B64':
    return '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='


@pytest.fixture
def another_digest_str() -> 'SHA256B64':
    return '50DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='
