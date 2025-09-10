# S3DocumentStore

Module: `store.s3_store`

S3DocumentStore provides an asynchronous facade over S3 to persist and manage document artifacts. It focuses strictly on storage responsibilities:

- Store the original binary file (e.g., PDF)
- Store the normalized markdown copy
- Deterministic, idempotent S3 keys based on collection and document_id
- List, load, and delete stored artifacts

Parsing, chunking, embeddings, and RAG extraction are out of scope for this component.

## Key concepts

| Concept         | Description                                                                                   |
|-----------------|-----------------------------------------------------------------------------------------------|
| document_id     | Stable identifier for a document; should be the binary_hash computed upstream for idempotency.|
| base_path       | Prefix under which artifacts are stored (e.g., `uploads`).                                    |
| collection      | Logical domain namespace (see `vectorstore.models.CollectionEnum`).                            |
| original vs md  | Store both the original binary (optionally gzipped for PDFs) and a markdown copy.             |

## Settings / Configuration

Reads configuration from application settings (see `core.config.get_settings()`):

- aws_s3_bucket: Target bucket name
- aws_region: AWS region for the S3 client
- aws_s3_path: Default base prefix (used when store instance doesn’t override base_path)

Provide AWS credentials via standard environment or local emulator configuration.

## Public API summary

- save_original — Upload the original file to a deterministic key.
- save_markdown — Upload markdown as UTF-8 with text/markdown content type.
- info — List objects and return per-file metadata.
- load — Fetch object bytes by key.
- delete — Delete artifacts by document_id.

## Quick Reference

| Method         | Purpose                                                        | Returns          |
|----------------|----------------------------------------------------------------|------------------|
| save_original  | Upload original file; optional gzip for PDFs; idempotent keys. | S3ArtifactInfo   |
| save_markdown  | Upload markdown text as UTF-8 with content-type set.          | S3ArtifactInfo   |
| info           | List objects + metadata for a document_id.                    | dict             |
| load           | Download bytes for a specific key.                            | bytes            |
| delete         | Delete artifacts under the document prefix.                   | bool             |

### save_original
`save_original(file_path: str, *, document_id: str | None = None, compress: bool | None = None, content_type: str | None = None, extra_metadata: dict | None = None) -> S3ArtifactInfo  [async]`

Uploads the original file to a deterministic key. If `compress=True` and the path ends with `.pdf`, uploads gzipped with `ContentEncoding=gzip`. Content-Type defaults for PDFs unless overridden. Optional user metadata is attached.

<details>
<summary>Example</summary>

```python
saved = await store.save_original("/path/to/report.pdf", compress=True)
print(saved.document_id, saved.original_key)
```
</details>

### save_markdown
`save_markdown(md_text: str, *, document_id: str, extra_metadata: dict | None = None) -> S3ArtifactInfo  [async]`

Uploads markdown using UTF-8 and `text/markdown; charset=utf-8`. Optional user metadata is attached.

<details>
<summary>Example</summary>

```python
import services.upload_steps

await services.upload_steps.save_markdown("# Title\nHello", document_id=saved.document_id)
```
</details>

### info
`info(document_id: str) -> dict  [async]`

Lists objects under the deterministic prefix for the given document and returns keys plus per-file metadata (size, content type/encoding, last_modified, user metadata).

<details>
<summary>Example</summary>

```python
meta = await store.info(saved.document_id)
print([f["key"] for f in meta["files"]])
```
</details>

### load
`load(key: str) -> bytes  [async]`

Downloads the object bytes for a given S3 key.

<details>
<summary>Example</summary>

```python
markdown_bytes = await store.load(meta["files"][0]["key"])  # choose from info()
```
</details>

### delete
`delete(document_id: str, *, delete_original: bool = True, delete_markdown: bool = True) -> bool  [async]`

Deletes one or both artifacts stored under the document prefix. Returns True if successful or if nothing existed.

<details>
<summary>Example</summary>

```python
await store.delete(saved.document_id)
```
</details>

## Storage flow

1) Determine document_id (ideally the upstream binary_hash for idempotency).
2) Construct deterministic keys under `{base_path}/{collection}/{document_id}/`.
3) Upload original (optionally gzipped if PDF) and markdown with appropriate metadata.
4) Retrieve and list artifacts as needed; delete by document_id when required.

## Usage example

<details>
<summary>Full example</summary>

```python
import asyncio
from schemas.enums import CollectionEnum
from store.s3_store import S3Store


async def main():
  store = S3Store(CollectionEnum.DEFAULT, base_path="uploads")

  # 1) Save original (gzipped) and markdown
  saved = await store.save_original("/path/to/report.pdf", compress=True)
  await store.save_markdown("# Title\nHello", document_id=saved.document_id)

  # 2) Inspect what’s stored
  meta = await store.info(saved.document_id)
  print([f["key"] for f in meta["files"]])

  # 3) Load bytes back
  b = await store.load(meta["files"][0]["key"])  # select a markdown key
  print(len(b))

  # 4) Delete artifacts
  await store.delete(saved.document_id)


if __name__ == "__main__":
  asyncio.run(main())
```
</details>

## Edge cases and examples

- Missing document_id for markdown save:
  - Behavior: `save_markdown` requires a `document_id` and will raise if absent.
- Non-PDF originals with `compress=True`:
  - Behavior: Uploads without gzip; compression only applies to `.pdf` files.
- Repeated saves with same document_id:
  - Behavior: Overwrites the same keys, supporting idempotent ingestion.

## Notes & best practices

- Always compute a stable `binary_hash` early and reuse it as the `document_id` across storage and vectorization steps.
- Include a correlation_id in logs at call sites and avoid logging raw contents.
- Keep `base_path` and `collection` stable to ensure predictable keys and lifecycle management.

## Errors & retries

- Underlying `aioboto3/botocore` exceptions may be raised (e.g., `NoSuchBucket`, `AccessDenied`). Map these to domain errors (e.g., `StorageError`) at the service boundary.
- Apply timeouts and retries with exponential backoff in orchestration layers for resilience.
