from __future__ import annotations

from pathlib import Path


def write_temp_file(file_bytes: bytes, filename: str, base_dir: str) -> Path:
    """Write bytes to a temp file under base_dir and return the path."""
    tmp_path = Path(base_dir) / filename
    tmp_path.write_bytes(file_bytes)
    return tmp_path
