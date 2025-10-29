from __future__ import annotations

from schemas.upload import JobStatus


def normalise_progress(step, percent, status):
    if status == JobStatus.COMPLETED:
        return 100, ''

    norm_step = step or None
    norm_percent = None if percent is None else max(0, min(100, int(percent)))
    return norm_percent, norm_step
