import uuid
import pytest

from app.api.schemas import AccessContext
from app.core.dependencies import access_scoped_session
from app.repositories import Document, Job, Ingestion
from app.repositories.schemas import DocumentCreate, CreateJobCmd
from app.schemas.upload import JobStatus
from app.vector.schemas import IngestionVersionInsert
from app.repositories.exceptions import DocumentNotFoundError, JobNotFoundError


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_cross_tenant_access_is_isolated(digest_random):
    # Tenant A, User U1 creates document, job, and ingestion rows
    tenant_a = uuid.UUID('00000000-0000-0000-0000-0000000000aa')
    user_u1 = uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01')
    ctx_a_u1 = AccessContext(tenant_id=tenant_a, user_id=user_u1)

    created = {}
    async for s_a_u1 in access_scoped_session(tenant=ctx_a_u1):
        # Create a document
        doc_id, _ = await Document.upsert(
            s_a_u1,
            data=DocumentCreate(
                collection='default',
                digest=digest_random,
                original_filename='mt-doc.pdf',
                content_type='application/pdf',
                size_bytes=42,
            ),
        )

        # Create a job linked to the document
        job_id, _ = await Job.upsert(
            s_a_u1,
            job=CreateJobCmd(
                status=JobStatus.PROCESSING,
                percent=0,
                step='start',
                digest=digest_random,
                document_uuid=doc_id,
                collection='default',
                original_filename='mt-doc.pdf',
                content_type='application/pdf',
                size_bytes=42,
            ),
        )

        # Create an ingestion record for the same (collection, digest)
        await Ingestion.create(
            s_a_u1,
            key=IngestionVersionInsert(
                collection='default',
                digest=digest_random,
                chunker_version='cv1',
                embed_model='em',
                embed_model_ver='v1',
            ),
        )

        # Keep the identifiers to check from another tenant
        created = {'doc_id': doc_id, 'job_id': job_id}

    # Tenant B, User V1 attempts to access Tenant A resources
    tenant_b = uuid.UUID('00000000-0000-0000-0000-0000000000bb')
    user_v1 = uuid.UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1')
    ctx_b_v1 = AccessContext(tenant_id=tenant_b, user_id=user_v1)

    async for s_b_v1 in access_scoped_session(tenant=ctx_b_v1):
        with pytest.raises(DocumentNotFoundError):
            await Document.get(s_b_v1, id=created['doc_id'])

        with pytest.raises(JobNotFoundError):
            await Job.status(s_b_v1, job_id=created['job_id'])

        # Ingestion.exists should be False under a different tenant
        exists = await Ingestion.exists(
            s_b_v1, digest=digest_random, collection='default'
        )
        assert exists is False


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_same_tenant_different_users_can_access(digest_random):
    # Tenant A, User U1 creates resources
    tenant_a = uuid.UUID('00000000-0000-0000-0000-0000000000aa')
    user_u1 = uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01')
    ctx_a_u1 = AccessContext(tenant_id=tenant_a, user_id=user_u1)

    created = {}
    async for s_a_u1 in access_scoped_session(tenant=ctx_a_u1):
        doc_id, _ = await Document.upsert(
            s_a_u1,
            data=DocumentCreate(
                collection='default',
                digest=digest_random,
                original_filename='mt-doc.pdf',
            ),
        )
        job_id, _ = await Job.upsert(
            s_a_u1,
            job=CreateJobCmd(
                status=JobStatus.PROCESSING,
                percent=0,
                step='start',
                digest=digest_random,
                document_uuid=doc_id,
                collection='default',
                original_filename='mt-doc.pdf',
                content_type='application/pdf',
                size_bytes=42,
            ),
        )
        await Ingestion.create(
            s_a_u1,
            key=IngestionVersionInsert(
                collection='default',
                digest=digest_random,
                chunker_version='cv1',
                embed_model='em',
                embed_model_ver='v1',
            ),
        )
        created = {'doc_id': doc_id, 'job_id': job_id}

    # Same tenant A, different user U2 should be able to read
    user_u2 = uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa02')
    ctx_a_u2 = AccessContext(tenant_id=tenant_a, user_id=user_u2)

    async for s_a_u2 in access_scoped_session(tenant=ctx_a_u2):
        doc = await Document.get(s_a_u2, id=created['doc_id'])
        assert doc.digest == digest_random
        assert doc.collection == 'default'

        status = await Job.status(s_a_u2, job_id=created['job_id'])
        assert status is not None
        assert status.job_id == created['job_id']

        exists = await Ingestion.exists(
            s_a_u2, digest=digest_random, collection='default'
        )
        assert exists is True
