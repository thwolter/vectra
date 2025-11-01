# DocumentIngestor

`src/vector/ingestor.py`

Implements the ingestion contract for converting parsed documents into vector embeddings. Used by `UploadPipeline.ingest_documents`.

## Construction

```python
from vector.ingestor import DocumentIngestor

ingestor = DocumentIngestor(collection="default")
```

Optional repositories (`ingestion_repo`, `job_repo`) can be injected for testing.

## ingest(session, docs, job_id)

1. Loads the job to retrieve the owning document ID and digest.
2. Short-circuits when `docs` is empty, returning an `IngestionResult` flagged `skipped=True`.
3. Checks for existing embeddings via `embeddings_exist`:
   - Computes an `IngestionVersion` (parser/chunker/embedding fingerprints + collection).
   - Delegates to `IngestionRepository.exists` to detect configuration matches.
4. When embeddings are absent:
   - Builds batches using `batch_documents_by_tokens`.
   - Enriches metadata (`digest`, `chunk_id`) for each chunk.
   - Writes batches into the vector store returned by `get_vectorstore`, scoped to the tenant ID on the session.
   - Persists an `IngestionCreate` record referencing the job and document.

Any `EmbeddingsAlreadyExistError` propagates to the caller; `UploadPipeline` treats it as a skip so jobs finish successfully.

## Helper Methods

| Method | Description |
| --- | --- |
| `enrich_metadata(batch, digest, offset)` | Mutates each document's metadata to include `chunk_id` and `digest`. |
| `batch_documents_by_tokens(docs)` | Uses `vector.batching.batch_documents_by_tokens` to honour token/doc limits. |
| `mark_ingestion(session, job, digest)` | Creates an ingestion record and returns its UUID. |
| `embeddings_exist(session, digest)` | Uses `IngestionRepository.exists` with the current ingestion version. |

## Tenant Awareness

`get_vectorstore` reads the tenant ID from `session.info['tenant_id']`, set by the `tenauth` access-scoped session factory (`src/core/db.session_factory`). This ensures each ingestion only sees and writes rows for the caller's tenant.
