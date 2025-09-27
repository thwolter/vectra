# syntax=docker/dockerfile:1

# Use official Python 3.12 slim image (matches requires-python >=3.12)
FROM python:3.12-slim as runtime

# Prevent Python from buffering stdout/stderr and writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH" \
    UVICORN_WORKERS=2 \
    PORT=8000

# System packages needed for common deps (psycopg2, opencv-headless/easyocr, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    libpq-dev \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel

WORKDIR /app

# Copy project files
COPY . /app

# Install project and dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Expose the FastAPI port (Coolify will map this)
EXPOSE 8000

# Copy entrypoint and set as default command
RUN chmod +x scripts/entrypoint.sh

# Default command: use entrypoint script (web-only by default)
CMD ["bash", "scripts/entrypoint.sh"]
