#!/usr/bin/env python3
from __future__ import annotations


import sys
from pathlib import Path

import typer

"""
Management CLI for backend tasks.

Notes:
- Uses Typer for command routing.
- Ensures `app/` is on sys.path so imports match the application runtime.
- Commands are stored in the `commands/` package and mounted here.
"""


# Ensure `app/` is importable when running from repo root
ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Import command groups
from commands.db import db  # noqa: E402

app = typer.Typer(help='Management CLI for database and maintenance tasks')
app.add_typer(db, name='db')


if __name__ == '__main__':
    app()  # Typer entry
