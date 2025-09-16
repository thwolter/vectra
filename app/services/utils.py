from __future__ import annotations

from app.schemas.upload import JobStatus


def normalise_progress(step, percent, status):
    if status == JobStatus.COMPLETED:
        return 100, ''
    else:
        if step is None or step == '':
            norm_step = None
        else:
            norm_step = step
        if percent is None:
            norm_percent = None
        else:
            norm_percent = max(0, min(100, int(percent)))
        return norm_percent, norm_step


async def assert_job_needs_review(job):
    if JobStatus(job.status) != JobStatus.NEEDS_REVIEW:
        raise ValueError(
            f"Review is only allowed when status is 'needs_review'; current status is '{job.status}'. Please continue processing the job first."
        )
