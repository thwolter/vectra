# IngestionRepository

`src/repositories/ingestion_repo.py`

Persists ingestion metadata for idempotency and audit trails.

## Purpose

- Track every successful vector ingestion run with metadata about the parser, chunker, embedding model, and originating job.
- Guard against duplicate embeddings by persisting parser/chunker/embedding fingerprints alongside the document digest.
- Provide lookup helpers for services (`UploadService`, `DocumentIngestor`) to skip redundant work.

## Key Methods

| Method | Description |
| --- | --- |
| `create(session, data)` | Inserts a new `IngestionRecord`, capturing tenant/user IDs from the scoped session. Rolls back on failure. |
| `get(session, ingestion_id)` | Fetches a record and refreshes relationships to `Document` and `Job`. Raises `RecordNotFoundError` when missing. |
| `delete(session, ingestion_id)` | Deletes an ingestion record, rolling back on errors and returning a boolean flag. |
| `find(session, collection, digest, version=None)` | Returns the newest ingestion for a digest, optionally scoped to a specific `IngestionVersion`. |
| `exists(session, collection, digest, version)` | Convenience boolean wrapper over `find` when testing a precise version match. |

## Ingestion Versions

`IngestionCreate.create` captures parser, chunker, and embedding fingerprints from the current settings. `IngestionVersion` bundles those values (plus the collection) so services can diff the requested run against the most recent ingestion and decide which stages to execute.

## Access Context

`create` introspects `AccessContext.from_session(session)` to populate `tenant_id` and `created_by`. For tests, construct the session via `access_scoped_session_ctx` to ensure the context is available.
