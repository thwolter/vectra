from typing import Protocol

from app.store.protocols import StoreProtocol
from app.schemas.enums import CollectionEnum  # or wherever this enum lives
from app.vector.protocols import IngestorProtocol


class StoreProvider(Protocol):
    def __call__(self, collection: CollectionEnum) -> StoreProtocol: ...


class IngestorProvider(Protocol):
    def __call__(
        self, *, collection: CollectionEnum, embedding_profile: str
    ) -> IngestorProtocol: ...
