# Vectorstore

pgvector-backed store for chunk embeddings.

- Collections: scoped by domain (e.g., `financial`).
- Deterministic IDs; deletes by resolved ids.
- Query scoping by `collection` and optional `source`; extraction uses `doc_id` for precision.

## Schemas and indexing

- Ensure `CREATE EXTENSION IF NOT EXISTS vector;`
- Indexes on `(collection, source)` and `(binary_hash)`.
