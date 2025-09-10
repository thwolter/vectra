# Ingestion

Overview of the ingestion pipeline and hash policy.

- Compute `binary_hash` before any storage or embeddings.
- Store original and markdown copies in S3.
- Chunk by semantic sections; embed and upsert to pgvector.

Diagram — Idempotency flow
<details>
<summary>Show idempotency flow</summary>

```mermaid
flowchart TD
    A[Upload] --> B[Compute binary_hash]
    B --> C{Hash exists?}
    C -- yes --> D[Skip]
    C -- no --> E[Store original in S3]
    E --> F[Parse to Markdown]
    F --> G[Store Markdown in S3]
    G --> H[Chunk + Embed]
    H --> I[Upsert to pgvector]
    I --> J[Run RAG enrichment]
```

</details>
