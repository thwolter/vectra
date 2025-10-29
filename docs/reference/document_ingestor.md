# DocumentIngestor

`app/vector/ingestor.py`

Implements the ingestion contract for converting parsed documents into vector embeddings. Used by `UploadPipeline.ingest_documents`.

## Construction

```python
from src.vector.ingestor import DocumentIngestor
from src.vector.models import IngestorSettings

ingestor = DocumentIngestor(
    collection="default",
    config=IngestorSettings(max_tokens_per_request=8192),
)
```

Optional repositories (`ingestion_repo`, `job_repo`) can be injected for testing.

## ingest(session, docs, job_id)

1. Loads the job to retrieve the owning document ID and digest.
2. Short-circuits when `docs` is empty, returning an `IngestionResult` flagged `skipped=True`.
3. Checks for existing embeddings via `embeddings_exist`:
   - Computes an `IngestionVersion` fingerprint from settings + collection.
   - Delegates to `IngestionRepository.exists`.
4. When embeddings are absent:
   - Builds batches using `batch_documents_by_tokens`.
   - Enriches metadata (`digest`, `chunk_id`) for each chunk.
   - Writes batches into the vector store returned by `get_vectorstore`, scoped to the tenant ID on the session.
   - Persists an `IngestionCreate` record referencing the job and document.

Any `EmbeddingsAlreadyExistError` propagates to the caller; `UploadPipeline` handles it by skipping the embed step without failing the job.

## Helper Methods

| Method | Description |
| --- | --- |
| `enrich_metadata(batch, digest, offset)` | Mutates each document's metadata to include `chunk_id` and `digest`. |
| `batch_documents_by_tokens(docs)` | Proxy to `BatchBuilder.batch_documents_by_tokens`. |
| `plan_batches(docs)` | Convenience helper for dry runs or logging. |
| `mark_ingestion(session, job, digest)` | Creates an ingestion record and returns its UUID. |
| `embeddings_exist(session, digest)` | Uses `IngestionRepository.exists` with the collection fingerprint. |

## Tenant Awareness

`get_vectorstore` reads the tenant ID from `session.info['tenant_id']`, set by the access-scoped session context in `app/core/dependencies`. This ensures each ingestion only sees and writes rows for the caller's tenant.
