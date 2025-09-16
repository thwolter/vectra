from __future__ import annotations

from typing import Any

from .schemas import ProposedMetadata


def merge_metadata(*, current: dict | ProposedMetadata, adjustments: dict) -> ProposedMetadata:
    """Apply human corrections to the job's proposed metadata.

    Validates inputs, does not mutate the given structures, and returns a
    new ProposedMetadata with the adjustments applied to the metadata field.
    Keys with value None in `adjustments` are ignored.

    Raises
    ------
    ValueError
        If `current` cannot be validated as ProposedMetadata or if
        `adjustments` is not a dict.
    """
    # Validate `current` into a ProposedMetadata instance
    try:
        current_pm: ProposedMetadata = (
            current if isinstance(current, ProposedMetadata) else ProposedMetadata.model_validate(current)
        )
    except Exception as exc:
        raise ValueError('current must be a ProposedMetadata-compatible dict') from exc

    if not isinstance(adjustments, dict):
        raise ValueError('adjustments must be a dict of field -> value')

    # Apply adjustments into a fresh copy, skip None values
    new_meta: dict[str, Any] = dict(current_pm.metadata or {})
    for k, v in adjustments.items():
        if v is not None:
            new_meta[k] = v

    return ProposedMetadata(
        metadata=new_meta,
        confidence=dict(current_pm.confidence or {}),
        conflicts=[],  # assume conflicts resolved after human review
    )
