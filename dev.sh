#!/bin/sh
uv run uvicorn app.main:app --reload --port 8010 &
uv run dramatiq app.main --processes 1 --threads 1 --watch &
wait