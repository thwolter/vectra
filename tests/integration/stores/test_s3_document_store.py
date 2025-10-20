import base64
import uuid
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.api.file import TemporaryUploadFile
from app.schemas.enums import CollectionEnum
from app.store import s3_store as module
from app.store.protocols import StoreProtocol
from app.store.s3_store import S3Store


@pytest.fixture
def base_prefix(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def store(base_prefix: str):
    return S3Store(CollectionEnum.DEFAULT.value, base_path=base_prefix)


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def document_digest() -> str:
    return base64.b64encode(uuid.uuid4().bytes).decode('ascii')


@pytest.fixture
def file(tiny_pdf_upload: UploadFile):
    return TemporaryUploadFile.from_upload(tiny_pdf_upload)


def test_local_store_conforms_runtime(tmp_path):
    store = S3Store(CollectionEnum.DEFAULT.value, base_path=tmp_path)
    assert isinstance(store, StoreProtocol)


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_save_original_and_delete_success(store, file, tenant_id, document_digest):
    document_id = uuid.uuid4()
    saved = await store.save_original(
        file,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    assert saved.original_key is not None

    info = await store.info(document_id=document_id, digest=document_digest, tenant_id=tenant_id)
    files = info.get('files', []) if isinstance(info, dict) else getattr(info, 'files', [])
    keys = [(f['key'] if isinstance(f, dict) else getattr(f, 'key', '')) for f in files]
    assert any(k.endswith('.pdf') or k.endswith('.pdf.gz') for k in keys)

    result = await store.delete(
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    assert result is True


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_save_markdown_then_load_and_delete_success(store, tenant_id, document_digest):
    content = '# Title\nHello world'
    document_id = uuid.uuid4()
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

    # Info should include markdown file with proper content type
    info = await store.info(document_id=document_id, digest=document_digest, tenant_id=tenant_id)
    files = info.get('files', []) if isinstance(info, dict) else getattr(info, 'files', [])
    md_files = [
        f for f in files if ((f['key'] if isinstance(f, dict) else getattr(f, 'key', '')).endswith('document.md'))
    ]
    assert len(md_files) == 1
    md_ctype = (
        md_files[0]['content_type'] if isinstance(md_files[0], dict) else getattr(md_files[0], 'content_type', '')
    )
    assert str(md_ctype).startswith('text/markdown')

    # Cleanup
    ok = await store.delete(
        document_id,
        digest=document_digest,
        tenant_id=tenant_id,
        delete_markdown=True,
        delete_original=False,
    )
    assert ok is True


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_info_with_both_files_success(store, file, tenant_id, document_digest):
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
    files = info.get('files', []) if isinstance(info, dict) else getattr(info, 'files', [])
    keys = [(f['key'] if isinstance(f, dict) else getattr(f, 'key', '')) for f in files]
    assert any(k.endswith('original.pdf') or k.endswith('original.pdf.gz') for k in keys)
    assert any(k.endswith('document.md') for k in keys)

    assert (
        await store.delete(
            document_id=document_id,
            digest=document_digest,
            tenant_id=tenant_id,
        )
    ) is True


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_load_failure_nonexistent_key_raises(store):
    with pytest.raises(Exception):
        await store.load('tests/nonexistent/key.txt')


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_info_failure_invalid_bucket(monkeypatch, base_prefix):
    # Create a store with valid base_prefix but force an invalid bucket name to trigger error

    monkeypatch.setattr(
        module.settings,
        'aws_s3_bucket',
        'definitely-nonexistent-bucket-vecapi-tests-12345',
        raising=False,
    )
    bad_store = S3Store(CollectionEnum.DEFAULT.value, base_path=base_prefix)
    with pytest.raises(Exception):
        await bad_store.info(
            document_id=uuid.uuid4(),
            digest=base64.b64encode(uuid.uuid4().bytes).decode('ascii'),
            tenant_id=uuid.uuid4(),
        )


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_save_failures_invalid_bucket(monkeypatch, base_prefix, apple_report_first_page_upload: UploadFile):
    # Force invalid bucket to cause save operations to fail

    monkeypatch.setattr(
        module.settings,
        'aws_s3_bucket',
        'definitely-nonexistent-bucket-vecapi-tests-67890',
        raising=False,
    )
    bad_store = S3Store(CollectionEnum.DEFAULT.value, base_path=base_prefix)

    # save_markdown should raise
    document_id = uuid.uuid4()
    with pytest.raises(Exception):
        await bad_store.save_markdown(
            'content',
            document_id=document_id,
            digest=base64.b64encode(uuid.uuid4().bytes).decode('ascii'),
            tenant_id=uuid.uuid4(),
        )

    # save_original with a real file should also raise due to bucket
    temp_file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    with pytest.raises(Exception):
        await bad_store.save_original(
            temp_file,
            document_id=document_id,
            digest=base64.b64encode(uuid.uuid4().bytes).decode('ascii'),
            tenant_id=uuid.uuid4(),
        )


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_head_returns_expected_metadata_s3(store, file, tenant_id, document_digest):
    document_id = uuid.uuid4()
    saved_orig = await store.save_original(
        file,
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

    # Head markdown
    md_meta = await store.head(saved_md.markdown_key)
    md_ctype = md_meta['content_type'] if isinstance(md_meta, dict) else getattr(md_meta, 'content_type', '')
    md_cenc = (
        md_meta.get('content_encoding') if isinstance(md_meta, dict) else getattr(md_meta, 'content_encoding', None)
    )
    md_size = md_meta.get('size') if isinstance(md_meta, dict) else getattr(md_meta, 'size', 0)
    md_meta_dict = md_meta.get('metadata') if isinstance(md_meta, dict) else getattr(md_meta, 'metadata', {})
    assert str(md_ctype).startswith('text/markdown')
    assert md_cenc in (None, '')
    assert isinstance(md_size, int) and md_size > 0
    assert isinstance(md_meta_dict, dict)

    # Head original
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
    assert orig_cenc in (None, 'gzip')
    assert isinstance(orig_size, int) and orig_size > 0

    # Cleanup
    await store.delete(document_id, digest=document_digest, tenant_id=tenant_id)


@pytest.mark.integration
@pytest.mark.needs_aws
@pytest.mark.asyncio
async def test_stream_matches_load_for_both_files_s3(store, file, tenant_id, document_digest):
    document_id = uuid.uuid4()
    saved_orig = await store.save_original(
        file,
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )
    saved_md = await store.save_markdown(
        '# Stream Test\ncontent',
        document_id=document_id,
        digest=document_digest,
        tenant_id=tenant_id,
    )

    # Stream markdown
    md_chunks = bytearray()
    async for chunk in store.stream(saved_md.markdown_key, chunk_size=8):
        md_chunks.extend(chunk)
    assert bytes(md_chunks) == await store.load(saved_md.markdown_key)

    # Stream original
    orig_chunks = bytearray()
    async for chunk in store.stream(saved_orig.original_key, chunk_size=1024):
        orig_chunks.extend(chunk)
    assert bytes(orig_chunks) == await store.load(saved_orig.original_key)

    # Cleanup
    await store.delete(document_id, digest=document_digest, tenant_id=tenant_id)
