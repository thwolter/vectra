from typing import Protocol

from schemas.enums import CollectionEnum  # or wherever this enum lives
from store.protocols import StoreProtocol
from vector.protocols import IngestorProtocol


class StoreProvider(Protocol):
    def __call__(self, collection: CollectionEnum) -> StoreProtocol: ...


class IngestorProvider(Protocol):
    def __call__(self, *, collection: CollectionEnum, embedding_profile: str) -> IngestorProtocol: ...
