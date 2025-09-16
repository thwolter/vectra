from __future__ import annotations

import pytest

from app.metadata.schemas import ProposedMetadata
from app.metadata.utils import merge_metadata


def _base_proposed_dict() -> dict:
    return {
        'metadata': {
            'company': 'Old Co',
            'financial_year': 2023,
        },
        'confidence': {},
        'conflicts': ['company'],
    }


def test_merge_overwrites_existing_keys() -> None:
    current = _base_proposed_dict()
    adjustments = {'company': 'New Co'}

    result = merge_metadata(current=current, adjustments=adjustments)

    assert isinstance(result, ProposedMetadata)
    assert result.metadata['company'] == 'New Co'
    # untouched fields remain
    assert result.metadata['financial_year'] == 2023


def test_merge_adds_missing_keys() -> None:
    current = _base_proposed_dict()
    adjustments = {'document_type': 'Annual Report'}

    result = merge_metadata(current=current, adjustments=adjustments)

    assert result.metadata['document_type'] == 'Annual Report'
    # existing values still present
    assert result.metadata['company'] == 'Old Co'
    assert result.metadata['financial_year'] == 2023


@pytest.mark.parametrize(
    'current,adjustments',
    [
        ('not a dict', {'company': 'X'}),  # invalid current
        ({'metadata': 'not a dict', 'confidence': {}, 'conflicts': []}, {'company': 'X'}),  # invalid structure
        (_base_proposed_dict(), None),  # invalid adjustments
        (_base_proposed_dict(), 'not a dict'),  # invalid adjustments type
    ],
)
def test_merge_raises_error_on_invalid_parameters(current, adjustments) -> None:
    with pytest.raises(ValueError):
        merge_metadata(current=current, adjustments=adjustments)
