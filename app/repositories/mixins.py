from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class EnsureTableMixin:
    _schema_ready: bool = False
    _schema_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, db_manager: Any):
        self.db_manager = db_manager

    async def _ensure_db(self) -> None:
        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()

    async def _ensure_schema_once(self, session: AsyncSession) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            await self._ensure_db()
            await self.db_manager.ensure_schema()
            self._schema_ready = True
