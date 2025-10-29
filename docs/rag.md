# RAG Agent Integration

VecAPI focuses on upstream ingestion so downstream Retrieval-Augmented Generation (RAG) agents can operate on clean, deduplicated knowledge bases. This page explains how the generated vectors and metadata support agent workflows.

## Data Products for Agents

Each successful upload yields:

- **Vector embeddings** stored in PGVector, namespaced by the profile's collection name.
- **Chunk metadata** containing:
  - `digest` — stable fingerprint for the source document.
  - `chunk_id` — incremental identifier assigned by `DocumentIngestor`.
  - `source` — original filename (or S3 key) for traceability.
- **Document metadata** available through `/v1/documents/{id}` and streaming endpoints for verbatim context.

Agents can combine these assets to retrieve context, ground responses, and present original artifacts for transparency.

## Querying the Vector Store

The vector store is instantiated with `app/vector/factory.get_vectorstore`, which returns a `langchain_postgres.PGVector` instance. In agent code you can reuse the same helper:

```python
from uuid import UUID
from src.vector.factory import get_vectorstore
from src.vector.models import IngestorSettings

tenant_id = UUID("...")  # Usually from the access token / session
vs = get_vectorstore(
    collection="default",
    tenant_id=tenant_id,
    config=IngestorSettings(embed_model="text-embedding-3-large"),
)

docs = vs.similarity_search("latest SEC 10-K revenue guidance", k=5)
```

All vector store connections include the tenant search path, so row-level security prevents cross-tenant leakage.

## Recommended Retrieval Pattern

1. **Select collection** — align with the processing profile associated with the user's workspace.
2. **Similarity search** — call `similarity_search`/`similarity_search_by_vector`.
3. **Re-rank (optional)** — apply domain-specific filters using `digest`, `chunk_id`, or custom metadata the parser emitted.
4. **Augment prompt** — combine retrieved snippets with content streamed from `/v1/documents/{id}/file/markdown` to provide full sections when needed.
5. **Answer generation** — feed the curated context into your LLM of choice, capturing the chunk metadata for citations.

## Keeping Agents Fresh

- Re-run uploads through VecAPI whenever the underlying source data changes. The ingestion fingerprint (`IngestionVersion`) guarantees idempotent reprocessing.
- Use `GET /v1/jobs/{job_id}` to monitor long-running ingestions and display progress to analysts.
- Schedule periodic scrapes or document sync tasks that call VecAPI programmatically; the API is built to be automation-friendly.

## Observability Hooks

OpenTelemetry spans from the worker are emitted with service name `vecapi-worker`. When debugging retrieval issues, correlate:

- Upload span (`process_upload_message`) with chunk ingestion.
- Application span (`POST /v1/uploads`) to confirm queueing.

Having both halves wired into your tracing backend simplifies root-cause analysis when an agent surfaces stale or missing context.
