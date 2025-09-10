from app.core.config import get_settings
from app.schemas.enums import CollectionEnum
from app.store.protocols import StoreProtocol


def default_store_provider(collection: CollectionEnum | None = None) -> StoreProtocol:
    """Return a DocumentStore instance based on current settings.

    This function calls get_settings() at runtime so tests can switch between
    S3 and LocalFileStore by changing settings (e.g., monkeypatching
    core.config.settings.document_store or the provider itself).
    """
    if not collection:
        collection = CollectionEnum.DEFAULT

    settings = get_settings()

    if settings.document_store == 'local':
        from app.store.local_store import LocalFileStore  # local import

        return LocalFileStore(collection=collection)  # type: ignore[bad-return]

    if settings.document_store == 's3':
        from app.store.s3_store import S3Store  # local import

        return S3Store(collection=collection)  # type: ignore[bad-return]

    raise ValueError(f'Unknown document store: {settings.document_store}')
