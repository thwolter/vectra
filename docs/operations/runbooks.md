# Runbooks

This page captures common operational scenarios and the steps to diagnose and recover VecAPI. Pair these runbooks with telemetry dashboards described in [Observability](../observability.md).

## Job Stuck in `PROCESSING`

**Symptoms**
- `/v1/jobs/{id}` reports `status=PROCESSING` for >15 minutes.
- `dramatiq_tasks_in_progress` remains non-zero with no completions.

**Checklist**
1. Inspect worker logs for the job id (`JOB_ID=<uuid>`).
2. Look for parser or embeddings timeouts. OpenAI rate limits surface as 429 or 5xx errors.
3. Confirm Redis connectivity; heartbeat keys (`worker:<host>:<pid>`) should refresh every 10 seconds.
4. If the process crashed, Dramatiq retries up to `DRAMATIQ_MAX_RETRIES`. Requeue manually if needed by constructing a fresh `ContinueProcessingInput` and calling `worker.dispatcher.enqueue_upload_processing` from an admin shell.

5. If the job is irrecoverable, mark it failed for client visibility:

```python
from services.factory import get_job_service
job_service = get_job_service()
await job_service.fail_job(session, job_id=<uuid>, exc=RuntimeError("manual"), last_step="manual_override")
```

## Upload Returns `409` or `status=DUPLICATED`

**Cause**: The SHA-256 digest already exists in the collection and a completed ingestion record is present.

**Actions**
1. Confirm this is expected (user re-uploading the same file). No action needed; the existing vectors remain valid.
2. To force reprocessing (e.g., changed parser), delete the ingestion record and re-upload:

```python
from repositories import ingestion_repository
await ingestion_repository.delete(session, ingestion_id=<uuid>)
```

Then retry the upload; the pipeline will run end-to-end.

## `s3_client` Errors or Missing Artifacts

**Symptoms**
- Worker logs: `Failed to update document URIs` or `botocore.exceptions`.
- Streaming routes (`/file/original`) return HTTP 404.

**Steps**
1. Verify AWS credentials and IAM permissions (PutObject/GetObject/DeleteObject).
2. Check bucket name/region — mismatches cause signature or redirect errors.
3. Inspect S3 for the expected key: `{collection}/{document_id}/original`.
4. If the object never reached S3, rerun the job:

```python
await upload_service.continue_processing(payload)
```

(Enqueue through Dramatiq in production; only run inline during maintenance.)

## OpenAI Rate Limiting

**Symptoms**
- Worker logs show HTTP 429 from embeddings or parser requests.
- `dramatiq_tasks_queue_depth` grows rapidly.

**Mitigation**
1. Reduce concurrency: lower `DRAMATIQ_THREADS` temporarily.
2. Upgrade your OpenAI quota or switch to a self-hosted embeddings provider by injecting a custom `Embeddings` instance.
3. Implement exponential backoff around embeddings calls if limits persist (roadmap item).

## Postgres RLS Failures

**Symptoms**
- API startup crashes with `RlsNotEnforcedError`.
- Queries fail with `permission denied for relation documents`.

**Resolution**
1. Do not run the app with a superuser role. Create a dedicated role with RLS enabled.
2. Ensure migrations set up the schema and RLS policies:

```bash
uv run alembic upgrade head
```

3. Verify the tenant id on the session (`SELECT current_setting('app.tenant_id');`). If empty, confirm `X-Tenant-Id` header reaches the API.

## Clearing a Failed Job

When a job fails and cannot be retried automatically:

1. Investigate root cause via logs and traces.
2. Soft-delete the document if the uploaded file is invalid:

```python
from services.factory import get_document_service
doc_service = get_document_service()
await doc_service.delete(session, document_id=<uuid>)
```

3. Notify the client; they can re-upload once the underlying issue is resolved.

## Rotating S3 Buckets or Changing Collection Names

1. Drain the worker queue to avoid in-flight jobs.
2. Update environment variables (`AWS_S3_BUCKET`, `EMBEDDING__COLLECTION`).
3. Redeploy web and worker services.
4. Validate by uploading a smoke-test document and confirming URIs return the new bucket path.

## Emergency Disablement

To pause ingestion without shutting the API down:

1. Scale the worker deployment to zero or set `START_WORKER=false` and redeploy.
2. The API will continue to accept uploads but queue them. Communicate expected delay to end users.
3. Bring the worker back online and monitor queue depth until whittled down.
