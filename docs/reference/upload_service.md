# UploadService

`app/services/upload_service.py`

Coordinates ingestion from the HTTP edge to background execution. It owns the orchestration between the `DocumentService`, `JobService`, repositories, and the `UploadPipeline`.

## Responsibilities

- Ensure a canonical `DocumentRecord` exists for the uploaded digest.
- Initialize jobs and enforce single active job per document.
- Detect running ingestions and reuse their job when possible.
- Enqueue heavy processing (`continue_processing`) on the Dramatiq worker.
- Drive step-wise progress updates during background execution.

## Construction

```python
from src.services.factory import get_upload_service
service = get_upload_service()
```

`get_upload_service` resolves the active processing profile, builds an `UploadPipeline` with the profile's parser/store/vector configuration, and injects it into `UploadService(collection=profile.collection, pipeline=pipeline)`.

## Key Methods

| Method | Description |
| --- | --- |
| `initiate_document_intake(session, payload)` | Computes digest, creates/fetches the document + job, and returns `UploadInitResponse`. |
| `_ensure_document(session, payload, digest)` | Calls `DocumentService.ensure_canonical_document` with metadata derived from the upload. |
| `_resolve_existing_job(session, document_id, digest)` | Checks for pending jobs or previous `IngestionVersion` records and returns an existing job when dedupe applies. |
| `_run_step(session, job_id, ctx, step)` | Helper to update progress, execute a pipeline step, and handle exceptions by failing the job. |
| `continue_processing(payload)` | Entry point for the worker; executes the five-step `UploadPipeline`. |

## Error Handling

- Exceptions raised by pipeline steps are logged and delegated to `JobService.fail_job`, preserving the last successful step.
- Unique constraint races (`UniqueViolationError`) in `_create_job` retry by fetching the active job, making uploads idempotent.
- `_fetch_job_by_id` swallows repository errors when checking prior ingestion records to avoid blocking fresh uploads.

## Background Context

The Dramatiq actor (`app/worker/actors.py`) deserializes a `ContinueProcessingInput`, instantiates `UploadService`, and calls `continue_processing`. Tenant isolation is derived from the serialized `AccessContext`, which scopes the SQLModel session and vector store DSN.

See also: [`UploadPipeline`](../ingestion.md) for step semantics.
