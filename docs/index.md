# VecAPI Backend Documentation

This site documents the FastAPI backend that powers Financials_RAG. It covers ingestion, S3 storage, vectorstore, and the document-info extraction agent.

- Async-first architecture with strict typing and loguru-based structured logging.
- Idempotent ingestion pipeline using a precomputed binary hash.
- Storage of both original files and normalized markdown in S3.
- Vector embeddings in PostgreSQL with pgvector.

See the Ingestion & S3 Storage page for details about how original files and markdown are handled, including the S3DocumentStore.
