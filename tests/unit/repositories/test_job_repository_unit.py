import uuid

import pytest

from app.repositories import Job


@pytest.mark.asyncio
async def test_delete_by_job_id_executes_and_commits(fake_session_class):
    # Simulate ORM delete path with an existing job using shared FakeSession
    jid = uuid.uuid4()
    fake_session = fake_session_class(orm_exists=True)

    deleted = await Job.delete(session=fake_session, job_id=jid)

    assert deleted is True
    assert fake_session.deletes == 1
    assert fake_session._deleted_obj is not None
    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_delete_returns_false_when_no_row(fake_session_class):
    jid = uuid.uuid4()
    fake_session = fake_session_class(orm_exists=False)

    deleted = await Job.delete(fake_session, job_id=jid)

    assert deleted is False
    # No delete should have been issued when the row doesn't exist
    assert fake_session.deletes == 0
    # Commit should not be called when nothing is deleted (function returns early)
    assert fake_session.commits == 0
