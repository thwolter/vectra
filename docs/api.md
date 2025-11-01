# HTTP API

VecAPI exposes versioned REST endpoints under `/v1`. Every request must include an access context that identifies the tenant and user so database sessions run within row-level security constraints.

## Authentication & Access Context

| Header | Description |
| --- | --- |
| `Authorization: Bearer <token>` | Validated by `require_auth`; token should encode tenant metadata or map to directory claims. |
| `X-Tenant-Id` | UUID that scopes SQLModel sessions, PGVector connections, and storage keys. |
| `X-Tenant-User` | Identifier for auditing (`created_by`). |
| `X-Tenant-Role` (optional) | Downstream services can use the role to tailor responses. |

`src/api/utils.py` reads these headers into `AccessContext` objects that are serialized when enqueuing Dramatiq jobs.

### Example Request

```http
POST /v1/uploads HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-Id: 8b9fb1a4-5f89-4f56-9ec4-9f2b8f5ce90c
X-Tenant-User: analyst-42
Content-Type: multipart/form-data; boundary=---boundary
```

## Uploads (`POST /v1/uploads`)

- Accepts `multipart/form-data` with a single `file` field.
- Enforces file extension, MIME type, and size using `Settings.allowed_upload_files`.
- Workflow:
  1. Hash the file (`sha256_b64`) and ensure a canonical `DocumentRecord`.
  2. Initialise a `JobRecord` or reuse an existing in-progress job.
  3. Enqueue `ContinueProcessingInput` onto the Dramatiq broker.
- Response payload (`UploadInitResponse`):

```json
{
  "job_id": "ad45d7b0-a067-4c3b-99af-8b1741c7fb9d",
  "document_id": "15f39e5e-3c62-4d6b-a1ac-3dd2ae6ebf4a",
  "status": "QUEUED",
  "digest": "I2cM5t8z9RbxT6jM7z9cJQ==",
  "original_filename": "2024-Q1-report.pdf",
  "already_running": false
}
```

- Duplicate uploads may return `status=DUPLICATED` with `already_running=true`. Clients should surface this as “document already processed”.
- Error responses:
  - `413 Payload Too Large` — file exceeds `upload_size_limit`.
  - `415 Unsupported Media Type` — disallowed MIME type.
  - `409 Conflict` — existing ingestion version (parser/chunker/embedding fingerprints) detected.

## Job Status (`GET /v1/jobs/{job_id}`)

Returns `JobStatusResponse` with progress metadata:

```json
{
  "id": "ad45d7b0-a067-4c3b-99af-8b1741c7fb9d",
  "status": "PROCESSING",
  "percent": 50,
  "step": "store_markdown",
  "warnings": [],
  "errors": []
}
```

- Steps map to pipeline phases defined in `src/services/upload_steps.UploadPipeline`.
- When the job cannot be found (purged or unknown), a 404 response is returned.

## Documents

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/v1/documents/` | List documents with optional filters (`digest`, `collection`, pagination). |
| `GET` | `/v1/documents/{document_id}` | Fetch metadata, artifact URIs, status flags, and timestamps. |
| `DELETE` | `/v1/documents/{document_id}` | Soft-delete metadata and dissociate artifacts (upstream services should handle S3 cleanup if required). |

`DocumentService` handles URI generation by calling the configured store provider (`s3://` or `file://`). Pagination parameters mirror FastAPI defaults (`limit`, `offset`).

### Streaming Artifacts

- `GET /v1/documents/{document_id}/file/original`
- `GET /v1/documents/{document_id}/file/markdown`

Both endpoints stream binary content and set appropriate headers:

| Header | Source |
| --- | --- |
| `Content-Type` | Derived from stored metadata (`application/pdf`, `text/markdown`, …). |
| `Content-Length` | Provided by the store when available. |
| `Content-Encoding` | Set to `gzip` when originals are compressed. |
| `Content-Disposition` | Inline for Markdown; attachment for binaries. |

Failures to locate the artifact result in `404 Not Found`.

## Error Model

| Status | Trigger | Mitigation |
| --- | --- | --- |
| `400 Bad Request` | Invalid query params, missing headers, malformed multipart data. | Correct request payload. |
| `401 Unauthorized` | Missing/invalid bearer token. | Obtain a valid JWT or API token. |
| `403 Forbidden` | Tenant mismatch or insufficient role (future). | Ensure access context matches token claims. |
| `404 Not Found` | Unknown job, document, or artifact. | Verify identifiers; purge caches if recently deleted. |
| `409 Conflict` | Duplicate upload where ingestion already exists. | Surface friendly message or offer to reprocess. |
| `415 Unsupported Media Type` | File extension/MIME not allowlisted. | Convert or modify profiles. |
| `500 Internal Server Error` | Unexpected exceptions. See logs and OpenTelemetry traces for diagnostics. |

All error payloads follow FastAPI’s standard schema unless explicitly handled inside the route.
