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

Use the same helper the worker relies on: `vector.factory.get_vectorstore`. It returns a LangChain `PGVector` instance configured with the tenant’s schema.

```python
from uuid import UUID
from vector.factory import get_vectorstore

tenant_id = UUID("8b9fb1a4-5f89-4f56-9ec4-9f2b8f5ce90c")
vectorstore = get_vectorstore(collection="default", tenant_id=tenant_id)

# Async API for agents running on asyncio stacks
docs = await vectorstore.asimilarity_search("latest SEC 10-K revenue guidance", k=5)
for doc in docs:
    print(doc.metadata["digest"], doc.metadata.get("header_title"))
```

When running synchronously, use `similarity_search` instead of `asimilarity_search`. All connections set `search_path` to the tenant schema and expose `app.tenant_id`, so Postgres RLS blocks cross-tenant access.

## Recommended Retrieval Pattern

1. **Select collection** — align with the processing profile associated with the user's workspace.
2. **Similarity search** — call `similarity_search`/`similarity_search_by_vector`.
3. **Re-rank (optional)** — apply domain-specific filters using `digest`, `chunk_id`, or custom metadata the parser emitted.
4. **Augment prompt** — combine retrieved snippets with content streamed from `/v1/documents/{id}/file/markdown` to provide full sections when needed.
5. **Answer generation** — feed the curated context into your LLM of choice, capturing the chunk metadata for citations.
6. **Audit** — optionally stream the original artifact (`/file/original`) to attach PDFs or Markdown to analyst workflows.

## Keeping Agents Fresh

- Re-run uploads through VecAPI whenever the underlying source data changes. The ingestion fingerprint (`IngestionVersion`) guarantees idempotent reprocessing.
- Use `GET /v1/jobs/{job_id}` to monitor long-running ingestions and display progress to analysts.
- Schedule periodic scrapes or document sync tasks that call VecAPI programmatically; the API is built to be automation-friendly.

## Observability Hooks

OpenTelemetry spans from the worker are emitted with service name `vecapi-worker`. When debugging retrieval issues, correlate:

- Upload span (`process_upload_message`) with chunk ingestion.
- Application span (`POST /v1/uploads`) to confirm queueing.

Having both halves wired into your tracing backend simplifies root-cause analysis when an agent surfaces stale or missing context.
