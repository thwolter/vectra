# Vector Store Integration

Embedding and retrieval are handled by the `src/vector` package. The worker transforms parsed documents into embeddings, writes them to PGVector, and records ingestion fingerprints to prevent duplicates. This page explains how the components fit together and how to extend them.

## DocumentIngestor (`src/vector/ingestor.py`)

- Loads the owning job to resolve the document digest and tenant context.
- Skips ingestion when no documents are provided (e.g., parser returned nothing).
- Checks for existing embeddings by computing an `IngestionVersion` fingerprint (`collection + settings snapshot`). If present, raises `EmbeddingsAlreadyExistError`.
- Batches documents with `batch_documents_by_tokens`, updates metadata (`chunk_id`, `digest`), and calls `PGVector.aadd_documents`.
- Records the run via `IngestionRepository.create`, storing the job id and configuration fingerprint.

### Metadata Contract

Every chunk is augmented with:

- `digest` — SHA-256 hash of the original file.
- `chunk_id` — Monotonically increasing integer per document.
- Optional heading metadata (`header_title`, `header_level`, `header_index`) when provided by the parser.

These fields enable deterministic re-ingestion and downstream citations.

## Vector Store Factory (`src/vector/factory.py`)

`get_vectorstore(collection, tenant_id, embeddings=None)` builds a `langchain_postgres.PGVector` instance:

- Uses the async DSN (`postgresql+asyncpg`) from settings.
- Injects tenant metadata into server settings (`app.tenant_id`, `search_path`).
- Defaults to `OpenAIEmbeddings(model=settings.embedding.model)`, but callers can supply any LangChain `Embeddings` implementation.
- Does not create extensions automatically (`create_extension=False`); ensure `pgvector` is installed via migrations.

### Supplying Custom Embeddings

```python
from langchain_openai import AzureOpenAIEmbeddings
from vector.factory import get_vectorstore

embeddings = AzureOpenAIEmbeddings(
    azure_endpoint="https://...openai.azure.com",
    azure_deployment="text-embed",
)
vs = get_vectorstore("financials", tenant_id=tenant_uuid, embeddings=embeddings)
```

## Batching Strategy (`src/vector/batching.py`)

- Respects two limits from `Settings.embedding`:
  - `max_tokens_per_request`
  - `max_docs_per_batch`
- Drops documents that exceed the token limit individually, logging a warning but allowing the job to complete.
- Uses `estimate_text_tokens` (≈4 chars/token heuristic) to avoid counting tokens client-side.

Tune these parameters per deployment to match provider quotas. For OpenAI `text-embedding-3-small`, the defaults (300 000 tokens / 100 docs) are safe for most uploads.

## Utilities (`src/vector/utils.py`)

- `validate_docs` filters out empty documents and reports reasons, simplifying parser testing.
- `estimate_docs_tokens` aggregates token counts across the batch for quick diagnostics.

## Querying Embeddings

Downstream consumers can reuse the same factory used by the worker:

```python
from uuid import UUID
from vector.factory import get_vectorstore

tenant_id = UUID("8b9fb1a4-5f89-4f56-9ec4-9f2b8f5ce90c")
vectorstore = get_vectorstore(collection="default", tenant_id=tenant_id)
documents = await vectorstore.asimilarity_search("revenue guidance", k=5)
```

All queries honour tenant scoping because the connection sets `app.tenant_id` and the search path.

## Failure Handling

- Embedding errors bubble up; Dramatiq retries the actor up to `DRAMATIQ_MAX_RETRIES`.
- Network hiccups (Postgres or OpenAI) manifest as exceptions. Monitor `dramatiq_task_duration_seconds` and job failures to decide on additional retry logic or circuit breakers.
- When embeddings already exist, `EmbeddingsAlreadyExistError` is raised to prevent double writes. `UploadPipeline` catches this and treats the step as skipped.
