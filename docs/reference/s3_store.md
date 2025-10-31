# S3Store

`src/store/s3_store.py`

Implements the `StoreProtocol` against Amazon S3, handling compression, metadata, and deletion for document artifacts.

## Responsibilities

- Upload original files to a deterministic S3 prefix per collection and document.
- Optionally gzip-compress PDF originals while preserving content encoding metadata.
- Persist normalized Markdown copies with UTF-8 content type.
- Generate URIs used by `DocumentService.update_document_uris`.
- Delete artifacts when documents are purged.

## Layout

```
s3://{bucket}/{collection}/{document_id}/
    original.pdf (or original.pdf.gz)
    document.md
```

Keys are constructed via the `StoreKeyHelpers` mixin.

## Key Methods

| Method | Description |
| --- | --- |
| `save_original(file, document_id, compress=None)` | Streams the upload into S3 with `upload_fileobj`, optionally gzipping PDFs. Returns `ArtifactInfo` containing the original key. |
| `save_markdown(md_text, document_id)` | Uploads Markdown as `text/markdown; charset=utf-8`, returning the key in `ArtifactInfo`. |
| `delete(document_id, delete_original=True, delete_markdown=True)` | Lists objects under the document prefix and deletes relevant keys. Returns `True` when no fatal client errors occur. |
| `make_uri(key)` | Builds the `s3://` URI consumed by services. |

## Error Handling

- Upload failures are logged with structured metadata and re-raised, allowing callers to fail the job.
- Delete operations swallow object-not-found situations (`list_objects_v2` returns no results) and return `True`.
- Temporary files and gzip buffers are closed explicitly to avoid leaking descriptors.

## Local Development

Switch to the filesystem-backed store by registering `LocalFileStore` (see `src/store/local_store.py`) via the store provider. URI conversion uses `file://` instead of `s3://`, but the service APIs remain identical.
