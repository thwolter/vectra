import uuid

import pytest

from app.repositories.job_repository import Job


@pytest.mark.asyncio
async def test_delete_by_job_id_executes_and_commits(
    fake_session_class,
):
    # Simulate DELETE ... RETURNING with one row
    jid = uuid.uuid4()
    fake_session = fake_session_class(rows=[(jid,)])

    deleted = await Job.delete(session=fake_session, job_id=jid)

    assert deleted is True
    assert len(fake_session.executed) == 1
    sql, params = fake_session.executed[0]
    assert 'DELETE FROM upload_jobs' in sql
    assert params['id'] == jid
    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_delete_returns_false_when_no_row(
    fake_session_class,
):
    jid = uuid.uuid4()
    _session = fake_session_class(rows=[])  # no rows returned

    deleted = await Job.delete(_session, job_id=jid)

    assert deleted is False
    assert len(_session.executed) == 1
    sql, params = _session.executed[0]
    assert 'DELETE FROM upload_jobs' in sql
    assert 'RETURNING id' in sql
    assert params['id'] == jid
    assert _session.commits == 1
