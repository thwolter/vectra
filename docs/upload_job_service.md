# Upload job service

`UploadJobService`

The Upload job service orchestrates the ingestion workflow for a single uploaded file. It computes a stable binary hash, stores the original file and a markdown copy to S3, parses to structured chunks, and embeds them into the vector store. It also maintains a minimal in-memory job status to satisfy the API contract.

## Upload ingestion flow — Steps

1. **Receive upload:** Input: file bytes and optional *hints* (e.g., `company_hint`, `doc_type_hint`).
2. **Compute `binary_hash`:** Stable hash of the binary data for idempotency and deduplication.
3. **Initialize job:** Set status to *processing*, progress **0%**.
4. **Store original file to S3:** Persist the raw file including basic metadata.
5. **Parse → `list[Document]`:** Split the file into structured `Document` chunks (e.g., via Docling/LangChain).
6. **Save Markdown copy to S3:** Generate a readable Markdown version from the chunks and store it.
7. **Embed & upsert into pgvector:** Create embeddings and idempotently upsert them into the vector database.
8. **Finalize job:** Set status to *completed*, progress **100%**.

## Responsibilities

- Compute `binary_hash` before any storage (idempotency safety).
- Store both the original file and a markdown copy in S3 with metadata.
- Parse the file into `langchain_core.documents.Document` chunks.
- Embed and ingest documents into pgvector (deterministic IDs handled by ingestor).
- Maintain per-job status in memory and expose status/review operations.

## Public API

`init_upload(self, *, file_bytes: bytes, filename: str, content_type: str | None, hints: UploadHints) -> UploadInitResponse`

Initiates ingestion for an uploaded file. Returns `{ job_id, document_id, status, deduplicated, binary_hash }`.

`get_job_status(self, job_id: str) -> JobStatusResponse`

Returns current job status including progress and proposed metadata (if available).

`review_job(self, job_id: str, payload: JobReviewPayload) -> JobReviewResponse`

Accepts human review to confirm or correct extracted metadata (proposed metadata is initially derived from hints and later enrichment in the broader pipeline).

## Providers and protocols

UploadJobService depends on provider callables that return protocol implementations:

- `ParserProvider`: returns a `Parser` for the file to produce `ParseResult` with `documents: list[Document]`.
- `StoreProvider`: returns a `DocumentStore` to persist the original file and markdown copy.
- `IngestorProvider`: returns an `Ingestor` to embed/upsert documents into the vector store.

By default, providers are pulled from `providers.defaults` to use Docling parser, S3 store, and pgvector ingestor. See [Protocols](protocols.md) for exact interfaces and examples.

## Usage examples

### 1. Using the FastAPI endpoints

- `POST /v1/uploads` — upload a file. Form fields: `file` (UploadFile), `hints_json` (optional JSON string matching `UploadHints`). Optional header: `Idempotency-Key`.
- `GET /v1/jobs/{job_id}` — check job status.
- `PATCH /v1/jobs/{job_id}/review` — confirm or correct proposed metadata.

Example (shell)

```bash
curl -X POST \
  -F "file=@/path/to/report.pdf" \
  -F 'hints_json={"company_hint":"Acme Corp","reporting_year_hint":2024}' \
  http://localhost:8000/v1/uploads

# => {"job_id":"...","document_id":"...","status":"processing","binary_hash":"sha256:..."}

curl http://localhost:8000/v1/jobs/<job_id>

curl -X PATCH \
  -H 'Content-Type: application/json' \
  -d '{"confirm": true}' \
  http://localhost:8000/v1/jobs/<job_id>/review
```

### 2. Instantiating the service directly (Python)

```python
from services.upload_service import UploadService
from schemas.upload import UploadHints
from schemas.enums import CollectionEnum

svc = UploadService(
    collection=CollectionEnum.DEFAULT,
    parser=None,  # use providers.defaults
    store_provider=None,
    ingestor_provider=None,
)

file_bytes = open("./sample.pdf", "rb").read()
resp = await svc.process_document_upload(
    file_bytes=file_bytes,
    filename="sample.pdf",
    content_type="application/pdf",
    hints=UploadHints(company_hint="Acme"),
)

status = await svc.get_job_status(resp.job_id)
```

### 3. Wiring custom providers

You can supply your own implementations that satisfy the protocols:

```python
from protocols.providers import StoreProvider, IngestorProvider
from parsers.protocols import ParserProvider
from protocols.parsing import Parser
from protocols.store import DocumentStore
from protocols.ingestor import Ingestor
from schemas.enums import CollectionEnum


class MyParser(Parser):
    async def parse(self):
        # return ParseResult(documents=[...], source="s3://...")
        ...


class MyStore(DocumentStore):
    async def save_original(self, path: str, *, document_id: str, content_type: str | None):
        # upload to S3/MinIO; return an object with .original_key
        ...

    async def save_markdown(self, markdown_text: str, *, document_id: str) -> None:
        ...


class MyIngestor(Ingestor):
    async def ingest(self, docs: list[object]) -> str | None:
        # embed and upsert into your vector store
        ...


def my_parser_provider(*, file_path: str, source: str, profile: str) -> Parser:
    return MyParser()


def my_store_provider() -> DocumentStore:
    return MyStore()


def my_ingestor_provider(*, collection: CollectionEnum, embedding_profile: str) -> Ingestor:
    return MyIngestor()


svc = UploadJobService(
    collection=CollectionEnum.DEFAULT,
    parser_provider=my_parser_provider,
    store_provider=my_store_provider,
    ingestor_provider=my_ingestor_provider,
)
```

## Hints and idempotency

- Hints allow callers to pass optional routing and extraction clues (`company_hint`, `doc_type_hint`, `reporting_year_hint`, `parser_profile`, `embedding_profile`, etc.).
- The service computes `binary_hash` from the uploaded bytes before any storage. The returned `document_id` is derived deterministically (hex digest). Use this for idempotent handling downstream and S3 keying.
- The in-memory job status is ephemeral. In production, persist job state to a durable store if needed.

## Error handling and logging

- All steps log structured events with `loguru` including `binary_hash` and `collection`. Avoid logging raw file content.
- The service returns `failed` status for unknown job IDs in `get_job_status`.

## Related

- See [Ingestion](ingestion.md) for the broader pipeline and idempotency policy.
- See [Protocols](protocols.md) for protocol signatures and concrete examples.
