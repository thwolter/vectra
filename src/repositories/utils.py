from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from repositories.models import BaseSQLModel

T = TypeVar('T', bound=BaseSQLModel)


async def update_record(record: T, *, data: BaseModel, exclude_none: bool = True) -> T:
    """Apply partial updates from a Pydantic model onto a SQLModel record."""

    updates = data.model_dump(exclude_unset=True, exclude_none=exclude_none, exclude={'id'}, mode='json')
    for k, v in updates.items():
        setattr(record, k, v)
    return record
