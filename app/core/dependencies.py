"""
Dependency factories for database access and repositories.

This module centralizes construction of the global DatabaseManager and
small factory helpers for repositories, following the project guideline:
"Collect Dependency factories in core/dependencies.py".
"""

from __future__ import annotations

from typing import Optional

from app.core.database import DatabaseManager

# Global database manager instance (singleton within process)
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global DatabaseManager singleton.

    Ensures a single DatabaseManager instance is reused across the process.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


__all__ = [
    'get_database_manager',
]
