import base64
import uuid
from pathlib import Path

import pytest

from api.file import TemporaryUploadFile
from schemas.enums import CollectionEnum
from store.local_store import LocalFileStore
from store.protocols import StoreProtocol

# Helpers to make tests resilient whether info() returns dicts or Pydantic models


def _files_from_info(info):
    if isinstance(info, dict):
        return info.get('files', [])
    return getattr(info, 'files', []) or []


def _key_of(f):
    return f['key'] if isinstance(f, dict) else getattr(f, 'key', None)


def _ctype_of(f):
    return f['content_type'] if isinstance(f, dict) else getattr(f, 'content_type', None)


@pytest.fixture
def base_prefix(tmp_path) -> Path:
    return tmp_path / 'local-tests'


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def document_digest() -> str:
    return base64.b64encode(uuid.uuid4().bytes).decode('ascii')


def test_local_store_conforms_runtime(tmp_path):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=tmp_path)
    assert isinstance(store, StoreProtocol)


@pytest.mark.integration
async def test_save_original_and_delete_success(
    base_prefix,
    apple_report_first_page_upload,
    tenant_id,
    document_digest,
):
    document_id = uuid.uuid4()
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=base_prefix)
    file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)

    saved = await store.save_original(
        file,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    assert saved.original_key is not None
    key = saved.original_key

    assert Path(key).exists()

    info = await store.info(document_id=document_id, digest=document_digest, tenant_id=tenant_id)
    files = _files_from_info(info)
    assert any((_key_of(f) or '').endswith('.pdf') or (_key_of(f) or '').endswith('.pdf.gz') for f in files)

    ok = await store.delete(
        saved.document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    assert ok is True


@pytest.mark.integration
async def test_save_markdown_then_load_and_delete_success(base_prefix, tenant_id, document_digest):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=str(base_prefix))

    document_id = uuid.uuid4()
    content = '# Title\nHello world'
    saved_md = await store.save_markdown(
        content,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    assert saved_md.markdown_key is not None

    # Load back markdown and compare content
    data = await store.load(saved_md.markdown_key)
    assert data.decode('utf-8') == content

    # Info should include markdown file with content type
    info = await store.info(document_id=document_id, digest=document_digest, tenant_id=tenant_id)
    files = _files_from_info(info)
    md_files = [f for f in files if (_key_of(f) or '').endswith('document.md')]
    assert len(md_files) == 1
    assert (_ctype_of(md_files[0]) or '').startswith('text/markdown')

    # Cleanup (only markdown exists)
    ok = await store.delete(
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
        delete_markdown=True,
        delete_original=False,
    )
    assert ok is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_info_with_both_files_success(
    base_prefix,
    apple_report_first_page_upload,
    tenant_id,
    document_digest,
):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=base_prefix)
    file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)

    document_id = uuid.uuid4()
    await store.save_original(
        file,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
        compress=True,
    )
    await store.save_markdown(
        '# Doc\ncontent',
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )

    info = await store.info(document_id=document_id, digest=document_digest, tenant_id=tenant_id)
    files = _files_from_info(info)
    keys = [(_key_of(f) or '') for f in files]
    assert any(k.endswith('original.pdf') or k.endswith('original.pdf.gz') for k in keys)
    assert any(k.endswith('document.md') for k in keys)

    assert (
        await store.delete(
            document_id=document_id,
            digest=document_digest,
            tenant_id=tenant_id,
        )
        is True
    )


@pytest.mark.integration
async def test_load_failure_nonexistent_key_raises(base_prefix):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=base_prefix)

    with pytest.raises(Exception):
        await store.load(str(base_prefix / 'does-not-exist.txt'))


@pytest.mark.integration
async def test_make_uri_returns_file_scheme(
    base_prefix,
    apple_report_first_page_upload,
    tenant_id,
    document_digest,
):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=base_prefix)

    file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    document_id = uuid.uuid4()

    saved = await store.save_original(
        file,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    uri = store.make_uri(saved.original_key or '')
    assert uri.startswith('file://')


@pytest.mark.integration
async def test_head_returns_expected_metadata(
    base_prefix,
    apple_report_first_page_upload,
    tenant_id,
    document_digest,
):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=base_prefix)
    document_id = uuid.uuid4()

    upload = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    saved_orig = await store.save_original(
        upload,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    saved_md = await store.save_markdown(
        '# Head Test\ncontent',
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )

    # Head for markdown
    if saved_md.markdown_key is None:
        raise Exception('Markdown key is None')

    md_meta = await store.head(saved_md.markdown_key)
    md_ctype = md_meta['content_type'] if isinstance(md_meta, dict) else getattr(md_meta, 'content_type', '')
    md_cenc = (
        md_meta.get('content_encoding') if isinstance(md_meta, dict) else getattr(md_meta, 'content_encoding', None)
    )
    md_size = md_meta.get('size') if isinstance(md_meta, dict) else getattr(md_meta, 'size', 0)
    md_metadata = md_meta.get('metadata') if isinstance(md_meta, dict) else getattr(md_meta, 'metadata', {})
    assert str(md_ctype).startswith('text/markdown')
    assert md_cenc is None
    assert isinstance(md_size, int) and md_size > 0
    assert isinstance(md_metadata, dict)

    # Head for original (non-gzipped expected by default)
    assert saved_orig.original_key is not None
    orig_meta = await store.head(saved_orig.original_key)
    orig_ctype = orig_meta['content_type'] if isinstance(orig_meta, dict) else getattr(orig_meta, 'content_type', '')
    orig_cenc = (
        orig_meta.get('content_encoding')
        if isinstance(orig_meta, dict)
        else getattr(orig_meta, 'content_encoding', None)
    )
    orig_size = orig_meta.get('size') if isinstance(orig_meta, dict) else getattr(orig_meta, 'size', 0)
    assert str(orig_ctype).startswith('application/pdf')
    # Could be None when not gzipped
    assert orig_cenc in (None, 'gzip')
    assert isinstance(orig_size, int) and orig_size > 0


@pytest.mark.integration
async def test_stream_markdown_and_original_success(
    base_prefix,
    apple_report_first_page_upload,
    tenant_id,
    document_digest,
):
    store = LocalFileStore(CollectionEnum.DEFAULT.value, base_path=base_prefix)
    document_id = uuid.uuid4()

    # Save original (no gzip) and markdown
    upload = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    saved_orig = await store.save_original(
        upload,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    md_text = '# Stream Test\nHello streaming world'
    saved_md = await store.save_markdown(
        md_text,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )

    # Stream markdown and verify content
    assert saved_md.markdown_key is not None
    md_chunks: list[bytes] = []
    async for chunk in store.stream(saved_md.markdown_key, chunk_size=16):
        md_chunks.append(chunk)
    md_joined = b''.join(md_chunks).decode('utf-8')
    assert md_joined == md_text

    # Stream original and compare with load()
    assert saved_orig.original_key is not None
    orig_chunks: list[bytes] = []
    async for chunk in store.stream(saved_orig.original_key, chunk_size=16):
        orig_chunks.append(chunk)
    streamed_orig = b''.join(orig_chunks)
    loaded_orig = await store.load(saved_orig.original_key)
    assert streamed_orig == loaded_orig

    # Cleanup
    assert (
        await store.delete(
            document_id=document_id,
            digest=document_digest,
            tenant_id=tenant_id,
        )
    ) is True
