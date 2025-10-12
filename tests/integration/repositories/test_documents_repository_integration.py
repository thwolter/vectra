import pytest

from app.repositories import document_repository
from app.repositories.exceptions import RecordAlreadyExistsError, RecordNotFoundError
from app.repositories.schemas import DocumentCreate, DocumentUpdate


@pytest.mark.needs_postgres
async def test_can_create_document(session, document_created):
    result = await document_repository.get(session, document_id=document_created.id)
    assert result is not None
    assert result.id == document_created.id


@pytest.mark.needs_postgres
async def test_cannot_create_twice(session, document_created):
    data = DocumentCreate.model_validate(document_created.model_dump(mode='json'))
    with pytest.raises(RecordAlreadyExistsError):
        await document_repository.create(session, data=data)


@pytest.mark.needs_postgres
async def test_recreate_with_other_collection(session, document_created):
    data = DocumentCreate.model_validate(document_created.model_dump())
    data.collection = 'another'
    another_document = await document_repository.create(session, data=data)

    assert another_document.id is not None
    assert document_created.id != another_document.id
    session.delete(another_document)


@pytest.mark.needs_postgres
async def test_can_delete(session, document_created):
    deleted = await document_repository.delete(session, document_id=document_created.id)
    assert deleted is True

    with pytest.raises(RecordNotFoundError):
        await document_repository.get(session, document_id=document_created.id)

    # Second delete returns False (no-op)
    second = await document_repository.delete(session, document_id=document_created.id)
    assert second is False


@pytest.mark.needs_postgres
async def test_can_update(session, document_created):
    document = DocumentUpdate.model_validate(document_created)
    document.meta = {'foo': 'bar'}
    document.markdown_uri = 'https://example.com'
    updated_document = await document_repository.update(session, document=document)
    assert updated_document.meta == {**document_created.meta, 'foo': 'bar'}
    assert updated_document.markdown_uri == 'https://example.com'

    updated_document = await document_repository.update(session, document=document, replace_meta=True)
    assert updated_document.meta == {'foo': 'bar'}


@pytest.mark.needs_postgres
async def test_can_get_for_digest(session, document_created):
    record = await document_repository.get_for_digest(
        session,
        digest=document_created.digest,
        collection=document_created.collection,
    )
    assert record is not None
    assert record.id == document_created.id


@pytest.mark.needs_postgres
async def test_can_get_or_create(session, document_created):
    data = DocumentCreate.model_validate(document_created.model_dump())
    record, created = await document_repository.get_or_create(session, data=data)
    # Should return the existing record when it already exists
    assert record is not None
    assert created is False
    assert record.id == document_created.id
