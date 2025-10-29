# DocumentService

`app/services/document_service.py`

Acts as the boundary between HTTP routes and document persistence. It wraps repository calls with storage-aware behavior.

## Responsibilities

- Create or fetch canonical `DocumentRecord` entries keyed by digest and collection.
- Generate signed/object-store URIs for originals and Markdown companions.
- Stream stored artifacts while preserving metadata headers (size, content type, encoding).
- Provide list/get/delete operations for API routes.

## Construction

```python
from src.services.factory import get_document_service
document_service = get_document_service()
```

The default constructor wires the `default_store_provider('default')` and the shared `DocumentRepository`.

## Key Methods

| Method | Description |
| --- | --- |
| `ensure_canonical_document(session, data)` | Fetches or creates a document row, returning `(record, created_bool)`. |
| `update_document_uris(session, document_id, original_key, markdown_key)` | Converts store keys to URIs (`store.local_store.make_uri`) and persists them. |
| `stream_file(document_id, which)` | Resolves the appropriate artifact, fetches metadata, and returns `(streamer, FileInfo, key)`. |
| `get_document(session, document_id)` | Returns a `DocumentResponse` including collection, original filename, content type, size bytes, and artifact URIs. |
| `list_documents(session, filters)` | Streams results from the repository and coerces them into `DocumentListResponse`. |
| `delete(session, document_id)` | Deletes the document row; upstream callers should also handle artifact cleanup if needed. |

## Streaming Considerations

- Supports two `which` values: `'original'` and `'markdown'`.
- Raises `FileNotFoundError` when the requested artifact is missing, allowing API handlers to translate into HTTP 404.
- Uses the `StoreProtocol` to fetch metadata (content length, encoding) so streaming routes set accurate headers.

## Integration Points

- Upload pipeline uses `update_document_uris` after storing artifacts.
- Streaming API routes rely on `stream_file` to serve binary responses.
- Profiles may provide alternate store providers (e.g., local filesystem) without changing service code.
