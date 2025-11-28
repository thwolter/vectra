from __future__ import annotations

import uuid
from typing import Any, Sequence

from langchain_core.documents import Document
from langchain_postgres.vectorstores import Base, PGVector
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Index, String, select, text
from sqlalchemy.dialects.postgresql import JSON, JSONB, UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, relationship

_TENANT_AWARE_CLASSES: tuple[type[Any], type[Any]] | None = None


def _get_tenant_embedding_collection_store(
    vector_dimension: int | None = None,
) -> tuple[type[Any], type[Any]]:
    """Return tenant-aware ORM models mirroring our partitioned tables."""
    global _TENANT_AWARE_CLASSES
    if _TENANT_AWARE_CLASSES is not None:
        return _TENANT_AWARE_CLASSES

    class TenantCollectionStore(Base):
        __tablename__ = 'langchain_pg_collection'

        uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        name = Column(String, nullable=False, unique=True)
        cmetadata = Column(JSON)
        tenant_id = Column(
            UUID(as_uuid=True),
            nullable=False,
            server_default=text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        )

        embeddings = relationship(
            'TenantEmbeddingStore',
            back_populates='collection',
            passive_deletes=True,
        )

        @classmethod
        def get_by_name(cls, session: Session, name: str) -> TenantCollectionStore | None:
            return session.query(cls).filter(cls.name == name).first()

        @classmethod
        async def aget_by_name(cls, session: AsyncSession, name: str) -> TenantCollectionStore | None:
            result = await session.execute(select(TenantCollectionStore).where(cls.name == name))
            return result.scalars().first()

        @classmethod
        def get_or_create(
            cls,
            session: Session,
            name: str,
            cmetadata: dict | None = None,
        ) -> tuple[TenantCollectionStore, bool]:
            created = False
            collection = cls.get_by_name(session, name)
            if collection:
                return collection, created

            collection = cls(name=name, cmetadata=cmetadata)
            session.add(collection)
            session.commit()
            return collection, True

        @classmethod
        async def aget_or_create(
            cls,
            session: AsyncSession,
            name: str,
            cmetadata: dict | None = None,
        ) -> tuple[TenantCollectionStore, bool]:
            created = False
            collection = await cls.aget_by_name(session, name)
            if collection:
                return collection, created

            collection = cls(name=name, cmetadata=cmetadata)
            session.add(collection)
            await session.commit()
            return collection, True

    class TenantEmbeddingStore(Base):
        __tablename__ = 'langchain_pg_embedding'

        tenant_id = Column(
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
        )
        id = Column(String, primary_key=True)
        collection_id = Column(
            UUID(as_uuid=True),
            ForeignKey(f'{TenantCollectionStore.__tablename__}.uuid', ondelete='CASCADE'),
        )
        collection = relationship(TenantCollectionStore, back_populates='embeddings')

        embedding = Column(Vector(vector_dimension))
        document = Column(String, nullable=True)
        cmetadata = Column(JSONB, nullable=True)

        __table_args__ = (
            Index(
                'ix_cmetadata_gin',
                'cmetadata',
                postgresql_using='gin',
                postgresql_ops={'cmetadata': 'jsonb_path_ops'},
            ),
        )

    _TENANT_AWARE_CLASSES = (TenantEmbeddingStore, TenantCollectionStore)
    return _TENANT_AWARE_CLASSES


class TenantAwarePGVector(PGVector):
    """PGVector variant that uses tenant_id in the primary key/upserts."""

    def __post_init__(self) -> None:
        if self.create_extension:
            self.create_vector_extension()

        embedding_store, collection_store = _get_tenant_embedding_collection_store(self._embedding_length)
        self.CollectionStore = collection_store
        self.EmbeddingStore = embedding_store
        self.create_tables_if_not_exists()
        self.create_collection()

    async def __apost_init__(self) -> None:
        if self._async_init:
            return
        self._async_init = True

        embedding_store, collection_store = _get_tenant_embedding_collection_store(self._embedding_length)
        self.CollectionStore = collection_store
        self.EmbeddingStore = embedding_store
        if self.create_extension:
            await self.acreate_vector_extension()

            await self.acreate_tables_if_not_exists()
        await self.acreate_collection()

    def _results_to_docs_and_scores(self, results: Sequence[Any]) -> list[tuple[Document, float]]:
        """Support tenant-aware models whose class name differs from PGVector defaults."""
        docs: list[tuple[Document, float]] = []
        model_key = self.EmbeddingStore.__name__

        for result in results:
            mapping = getattr(result, '_mapping', None)
            if mapping:
                embedding_row = mapping.get(self.EmbeddingStore) or mapping.get(model_key)
                distance = mapping.get('distance')
            else:
                embedding_row = None
                distance = None

            if embedding_row is None and hasattr(result, model_key):
                embedding_row = getattr(result, model_key)
            if embedding_row is None and hasattr(result, 'EmbeddingStore'):
                embedding_row = result.EmbeddingStore  # type: ignore[attr-defined]
            if embedding_row is None and isinstance(result, (list, tuple)) and result:
                embedding_row = result[0]

            if distance is None and hasattr(result, 'distance'):
                distance = result.distance  # type: ignore[attr-defined]
            if distance is None and isinstance(result, (list, tuple)) and len(result) > 1:
                distance = result[1]

            if embedding_row is None:
                continue

            docs.append(
                (
                    Document(
                        id=str(embedding_row.id),
                        page_content=embedding_row.document,
                        metadata=embedding_row.cmetadata,
                    ),
                    distance if self.embeddings is not None else None,
                )
            )

        return docs

    def add_embeddings(
        self,
        texts: Sequence[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Sync add embeddings with composite (tenant_id, id) upserts."""
        assert not self._async_engine, 'This method must be called with sync_mode'
        ids_ = [str(uuid.uuid4()) if id is None else id for id in (ids or [None] * len(texts))]
        metadatas = metadatas or [{} for _ in texts]

        with self._make_sync_session() as session:  # type: ignore[arg-type]
            collection = self.get_collection(session)
            if not collection:
                raise ValueError('Collection not found')
            data = [
                {
                    'id': id,
                    'collection_id': collection.uuid,
                    'embedding': embedding,
                    'document': text,
                    'cmetadata': metadata or {},
                }
                for text, metadata, embedding, id in zip(texts, metadatas, embeddings, ids_)
            ]
            stmt = insert(self.EmbeddingStore).values(data)
            on_conflict_stmt = stmt.on_conflict_do_update(
                index_elements=['tenant_id', 'id'],
                set_={
                    'embedding': stmt.excluded.embedding,
                    'document': stmt.excluded.document,
                    'cmetadata': stmt.excluded.cmetadata,
                },
            )
            session.execute(on_conflict_stmt)
            session.commit()

        return ids_

    async def aadd_embeddings(
        self,
        texts: Sequence[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Async add embeddings with composite (tenant_id, id) upserts."""
        await self.__apost_init__()  # Lazy async init

        ids_ = [str(uuid.uuid4()) if id is None else id for id in (ids or [None] * len(texts))]
        metadatas = metadatas or [{} for _ in texts]

        async with self._make_async_session() as session:  # type: ignore[arg-type]
            collection = await self.aget_collection(session)
            if not collection:
                raise ValueError('Collection not found')
            data = [
                {
                    'id': id,
                    'collection_id': collection.uuid,
                    'embedding': embedding,
                    'document': text,
                    'cmetadata': metadata or {},
                }
                for text, metadata, embedding, id in zip(texts, metadatas, embeddings, ids_)
            ]
            stmt = insert(self.EmbeddingStore).values(data)
            on_conflict_stmt = stmt.on_conflict_do_update(
                index_elements=['tenant_id', 'id'],
                set_={
                    'embedding': stmt.excluded.embedding,
                    'document': stmt.excluded.document,
                    'cmetadata': stmt.excluded.cmetadata,
                },
            )
            await session.execute(on_conflict_stmt)
            await session.commit()

        return ids_
