from typing import cast

from app.core.config import get_settings
from app.store.protocols import StoreProtocol


def default_store_provider(
    collection: str,
) -> StoreProtocol:
    settings = get_settings()

    store: StoreProtocol
    if settings.document_store == 'local':
        from app.store.local_store import LocalFileStore  # local import

        store = cast(StoreProtocol, LocalFileStore(collection=collection))

    elif settings.document_store == 's3':
        from app.store.s3_store import S3Store  # local import

        store = cast(StoreProtocol, S3Store(collection=collection))

    else:
        raise ValueError(f'Unknown document store: {settings.document_store}')

    assert isinstance(store, StoreProtocol)
    return store
