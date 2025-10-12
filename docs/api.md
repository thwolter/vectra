# HTTP API

All endpoints live under the `/v1` prefix and require both authentication and an access context (tenant metadata injected via headers). The access context is converted to a scoped database session, so every request is automatically isolated by tenant.

## Authentication & Headers

- `Authorization: Bearer <token>` — validated by `require_auth`.
- `X-Tenant-Id`, `X-Tenant-User`, … — forwarded to Dramatiq jobs via `AccessContext` for row-level security.
- Uploads must be sent as `multipart/form-data`.

## Uploads

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/v1/uploads` | Initialize ingestion by hashing, deduping, and queuing background work. Returns `UploadInitResponse` with `job_id` and `document_id`. |

Payload requirements:

- Single `file` field (PDF, DOCX, TXT, XLSX when supported).
- Size capped by profile (`ProcessingProfileSettings.max_upload_size`).
- Unsupported types return `415 Unsupported Media Type`; oversize returns `413 Payload Too Large`.

The handler (`app/api/v1/upload_routes.py`) immediately enqueues `ContinueProcessingInput` on the Dramatiq broker. Use `job_id` to poll progress.

## Job Status

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/v1/jobs/{job_id}` | Return the job status, including percent, current step, warnings, and errors. |

`JobService.get_status` coerces the stored enum to `JobStatusResponse`, falling back to `job_not_found` when the job has been purged.

## Documents

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/v1/documents/{document_id}` | Fetch document metadata, URIs, and ingestion flags. |
| `GET` | `/v1/documents/` | List documents with query-string filters (digest, collection, pagination). |
| `DELETE` | `/v1/documents/{document_id}` | Soft-delete metadata and clear references for the collection. |

Streaming endpoints (served from `app/api/v1/streaming_routes.py`):

| Method | Path | Response | Notes |
| --- | --- | --- | --- |
| `GET` | `/v1/documents/{document_id}/file/original` | Binary stream | Streams the uploaded artifact; respects inline vs. attachment for common MIME types. |
| `GET` | `/v1/documents/{document_id}/file/markdown` | Binary stream | Streams normalized Markdown generated during parsing. |

Both endpoints source metadata from `DocumentService.stream_file`, which resolves S3 keys and emits content headers (`Content-Type`, `Content-Length`, `Content-Encoding`).

## Profiles

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/v1/profiles/` | Enumerate registered `ProcessingProfileSettings` so clients can choose upload constraints. |

Profiles define collection names, upload rules, and parser/vector overrides. They are registered on startup via `app/profiles/registry.py`.

## Error Model

- HTTP 400 — validation failures, bad query parameters, or attempts to stream an unknown artifact.
- HTTP 401/403 — authentication or authorization issues caught by dependencies.
- HTTP 404 — document or job not found.
- HTTP 409 — duplicate documents (rare; typically surfaced as `already_running = True` in the upload response).
- HTTP 500 — unexpected errors; check Loguru traces and OpenTelemetry spans.
