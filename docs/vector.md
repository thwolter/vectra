# Vector Store Integration

VecAPI embeds parsed documents into a PGVector-backed store, orchestrated by `app/vector`. The ingestion layer focuses on batching, metadata management, and embedding provider selection.

## DocumentIngestor

`DocumentIngestor` (`app/vector/ingestor.py`) implements `IngestorProtocol` and coordinates the lifecycle for a single upload:

- Fetches the owning `JobRecord` to resolve the document digest.
- Short-circuits when no documents were produced by the parser.
- Asserts idempotency via `IngestionRepository.exists` before writing embeddings.
- Enriches each chunk with `digest` and monotonically increasing `chunk_id`.
- Writes batches using the configured vector store (`get_vectorstore`) and records an `IngestionCreate` row to persist the run.

Failures bubble up to the upload pipeline, which marks the job failed and stops further processing.

## Batching Strategy

`BatchBuilder` groups LangChain `Document` objects into batches constrained by `IngestorSettings`:

- `max_tokens_per_request` — estimated using `vector.utils.estimate_text_tokens`.
- `max_docs_per_batch` — prevents imbalanced batches.
- Documents exceeding the token cap are skipped with warnings; the job still completes but logs the omission.

These settings are customizable per processing profile to respect downstream embedding provider limits.

## Embeddings & Vector Stores

`app/vector/factory.py` encapsulates vector store creation:

- Embeddings providers are registered via `register_embeddings_provider`. The default factory constructs `OpenAIEmbeddings` with the profile's `embed_model`.
- `get_vectorstore` returns a `PGVector` instance scoped to the tenant by mutating the DSN with `tenauth.tenancy.dsn_with_tenant` and enforcing the application schema (`APP_SCHEMA`) in the search path.
- Passing `IngestorSettings.embedding_provider` allows alternate embeddings (e.g., self-hosted models) without changing the ingestion code.

## Ingestion Records

`IngestionRepository` keeps a fingerprint (`IngestionVersion`) of each successful ingest. The upload pipeline queries this repository before invoking the ingestor so reruns can skip embedding and reuse existing vectors.

Refer to the [Document Ingestor reference](reference/document_ingestor.md) for method-level documentation.
