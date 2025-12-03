# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.13

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

WORKDIR /build

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
# Clone the shared `nexor` helper library so the build can install it directly.
RUN git clone --depth 1 --branch main https://github.com/thwolter/nexor.git /app/nexor

# Copy only resolver inputs to maximise cache hits
COPY pyproject.toml ./

# Create venv and install deps into it (pip installs into /opt/venv)
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --upgrade pip setuptools wheel \
    && "${VIRTUAL_ENV}/bin/pip" install /app/nexor \
    && "${VIRTUAL_ENV}/bin/pip" install .

# ---------- Final runtime image ----------
FROM base AS runtime

# Bring in the prebuilt virtualenv
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

EXPOSE 8000
# Copy application code and assets late to maximise layer reuse.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY src ./src
COPY scripts/entrypoint.sh ./scripts/entrypoint.sh
RUN chmod +x ./scripts/entrypoint.sh

ENTRYPOINT ["./scripts/entrypoint.sh"]
