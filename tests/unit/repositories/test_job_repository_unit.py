import uuid

import pytest

from app.repositories.job_repository import JobRepository


@pytest.mark.asyncio
async def test_delete_by_job_id_executes_and_commits(
    fake_session_class, fake_db_manager_class
):
    # Simulate DELETE ... RETURNING with one row
    jid = uuid.uuid4()
    session = fake_session_class(rows=[(jid,)])
    repo = JobRepository(fake_db_manager_class(session))

    deleted = await repo.delete(job_id=jid)

    assert deleted is True
    assert len(session.executed) == 1
    sql, params = session.executed[0]
    assert 'DELETE FROM upload_jobs' in sql
    assert 'RETURNING job_id' in sql
    assert params['job_id'] == jid
    assert session.commits == 1


@pytest.mark.asyncio
async def test_delete_returns_false_when_no_row(
    fake_session_class, fake_db_manager_class
):
    jid = uuid.uuid4()
    session = fake_session_class(rows=[])  # no rows returned
    repo = JobRepository(fake_db_manager_class(session))

    deleted = await repo.delete(job_id=jid)

    assert deleted is False
    assert len(session.executed) == 1
    sql, params = session.executed[0]
    assert 'DELETE FROM upload_jobs' in sql
    assert 'RETURNING job_id' in sql
    assert params['job_id'] == jid
    assert session.commits == 1
