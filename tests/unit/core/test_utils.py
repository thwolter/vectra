import hashlib
import json

import pytest

from core.utils import FingerprintMixin


class DummyFingerprintModel(FingerprintMixin):
    name: str
    age: int
    active: bool


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_fingerprint_includes_all_fields_by_default():
    item = DummyFingerprintModel(name='alice', age=30, active=True)

    assert item.get_fingerprint() == _hash({'name': 'alice', 'age': 30, 'active': True})


class SelectiveFingerprintModel(FingerprintMixin):
    name: str
    age: int
    active: bool

    fingerprint_keys = ('name', 'active')


def test_fingerprint_uses_include_keys_when_defined():
    item = SelectiveFingerprintModel(name='alice', age=30, active=True)

    assert item.get_fingerprint() == _hash({'name': 'alice', 'active': True})


class ExcludeFingerprintModel(FingerprintMixin):
    name: str
    age: int
    active: bool

    fingerprint_exclude = ('age',)


def test_fingerprint_excludes_specified_fields():
    item = ExcludeFingerprintModel(name='alice', age=30, active=True)

    assert item.get_fingerprint() == _hash({'name': 'alice', 'active': True})


class OverlapFingerprintModel(FingerprintMixin):
    name: str
    age: int

    fingerprint_keys = ('name',)
    fingerprint_exclude = ('name',)


def test_fingerprint_raises_on_overlap_between_include_and_exclude():
    item = OverlapFingerprintModel(name='alice', age=30)

    with pytest.raises(ValueError, match='include and exclude'):
        item.get_fingerprint()


class UnknownIncludeFingerprintModel(FingerprintMixin):
    name: str

    fingerprint_keys = ('missing',)


def test_fingerprint_raises_when_include_references_unknown_field():
    item = UnknownIncludeFingerprintModel(name='alice')

    with pytest.raises(ValueError, match='unknown fields'):
        item.get_fingerprint()


class UnknownExcludeFingerprintModel(FingerprintMixin):
    name: str

    fingerprint_exclude = ('missing',)


def test_fingerprint_raises_when_exclude_references_unknown_field():
    item = UnknownExcludeFingerprintModel(name='alice')

    with pytest.raises(ValueError, match='unknown fields'):
        item.get_fingerprint()
