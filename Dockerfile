# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12

# ---------- Runtime base: minimal OS deps ----------
FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"


# Only runtime libs here
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpq5 ca-certificates git curl wget \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- Builder: compilers + headers ----------
FROM python:${PYTHON_VERSION}-slim AS build
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Build-time deps only
# libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 is only required for docling
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential gcc libpq-dev ca-certificates git \
      libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy only resolver inputs to maximise cache hits
COPY pyproject.toml ./

# Create venv and install deps into it (pip installs into /opt/venv)
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --upgrade pip setuptools wheel \
    && "${VIRTUAL_ENV}/bin/pip" install .

# ---------- Final runtime image ----------
FROM base AS runtime

# Bring in the prebuilt virtualenv
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# App code late to keep cache hot
COPY src ./app
COPY scripts ./scripts
COPY alembic.ini .
COPY alembic ./alembic

# Ensure entrypoint is executable and set permissions before dropping root
RUN chmod +x /src/scripts/entrypoint.sh && \
    useradd -m appuser && \
    chown -R appuser:appuser /src /opt/venv
USER appuser

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
# Examples:
#   START_WEB=true START_WORKER=false
#   START_WEB=false START_WORKER=true
