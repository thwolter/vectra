# JobService

`app/services/job_service.py`

Encapsulates job lifecycle rules for uploads, keeping the repository focused on persistence.

## Responsibilities

- Initialize jobs with canonical defaults (`PROCESSING`, `percent=0`, `step='hash'`).
- Clamp and monotonically increase progress updates.
- Enforce allowed status transitions (queued → processing → review/completed/failure).
- Record failures with contextual step information.
- Provide typed responses for polling clients.

## Usage

```python
from src.services.factory import get_job_service
job_service = get_job_service()
await job_service.update_status(
    session,
    job_id=job.id,
    status=JobStatus.COMPLETED,
    percent=100,
    step="update_s3_uris",
)
```

## Key Methods

| Method | Description |
| --- | --- |
| `init_job(session, job)` | Creates a `JobRecord` with normalized defaults, ignoring user-specified progress. |
| `update_progress(session, job_id, percent, step)` | Clamps the percent to `[0, 100]`, ensures monotonic increase, and normalizes empty step strings to `None`. |
| `update_status(session, job_id, status, percent=None, step=None)` | Validates transitions via `_ALLOWED`, normalizes percent/step with `normalise_progress`, and persists updates. |
| `fail_job(session, job_id, exc, last_step)` | Stores failure state while preserving the previous percent/step for diagnostics. |
| `get_status(session, job_id)` | Returns `JobStatusResponse` with warnings and errors attached. |
| `get_pending_or_create(session, document_id)` | Idempotently fetches or creates a job for a document, handling unique constraint races. |

## Progress Rules

- Raising `ValueError` when invalid transitions occur protects against race conditions between worker steps.
- `normalise_progress` (from `app/services/utils.py`) derives sensible defaults when setting terminal statuses (e.g., `percent=100` on `COMPLETED`).

## Cleanup

`delete_job` delegates to the repository and returns `True` when the row existed. Use this when purging stale jobs or responding to document deletion flows.
