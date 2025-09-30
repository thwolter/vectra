from __future__ import annotations

import os
import socket
from typing import Optional, Dict

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

try:
    # FastAPI instrumentation is optional (not needed for workers)
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
except Exception:  # pragma: no cover - optional dependency in some envs
    FastAPIInstrumentor = None  # type: ignore

# --- Internal singleton guard to avoid duplicate providers ---
_PROVIDER_INITIALISED = False


def _build_resource(
    *,
    service_name: str,
    service_namespace: Optional[str] = None,
    deployment_environment: Optional[str] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Resource:
    """Create a merged Resource that respects OTEL_RESOURCE_ATTRIBUTES env and adds sane defaults.

    The env-driven Resource (OTEL_RESOURCE_ATTRIBUTES) is merged automatically by Resource.create.
    We add instance id and any extra attributes on top.
    """
    attrs = {
        "service.name": service_name,
        "service.namespace": service_namespace or os.getenv("SERVICE_NAMESPACE", "finrag"),
        "deployment.environment": deployment_environment or os.getenv("DEPLOYMENT_ENV", "development"),
        "service.instance.id": os.getenv("SERVICE_INSTANCE_ID", f"{socket.gethostname()}:{os.getpid()}")
    }
    if extra:
        attrs.update(extra)
    return Resource.create(attrs)


def _ensure_provider(resource: Resource) -> TracerProvider:
    global _PROVIDER_INITIALISED
    provider = trace.get_tracer_provider()

    # If a real provider is not set yet (or we want to force our SDK provider), set it once.
    if not isinstance(provider, TracerProvider) or not _PROVIDER_INITIALISED:
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(OTLPSpanExporter())  # honours OTEL_* env vars
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _PROVIDER_INITIALISED = True
    else:
        # Merge/extend the resource if different calls add attributes.
        # The SDK doesn't support mutating resources; if already set, we keep the first one to avoid surprises.
        pass

    return provider


def init_otel_fastapi(app, *, service_name: str = "app", service_namespace: Optional[str] = None,
                      deployment_environment: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> None:
    """Initialise OpenTelemetry for the FastAPI web app.

    - Sets up the global TracerProvider with OTLP HTTP/protobuf exporter (config via env).
    - Instruments FastAPI request handling (if the instrumentation package is available).
    """
    resource = _build_resource(
        service_name=service_name,
        service_namespace=service_namespace,
        deployment_environment=deployment_environment,
        extra=extra,
    )
    _ensure_provider(resource)

    if FastAPIInstrumentor is not None:
        # Avoid double instrumentation when auto-instrumentation has been used accidentally.
        try:
            FastAPIInstrumentor().uninstrument_app(app)
        except Exception:
            pass
        FastAPIInstrumentor.instrument_app(app)


def init_otel_worker(*, service_name: str = "worker", service_namespace: Optional[str] = None,
                     deployment_environment: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> None:
    """Initialise OpenTelemetry for background workers (e.g., Dramatiq).

    This intentionally does not instrument FastAPI. If you want Dramatiq span context per-message,
    add a simple middleware around actor execution to create spans using `get_tracer()`.
    """
    resource = _build_resource(
        service_name=service_name,
        service_namespace=service_namespace,
        deployment_environment=deployment_environment,
        extra=extra,
    )
    _ensure_provider(resource)


def get_tracer(name: str):
    """Helper to obtain a tracer for manual spans in both app and worker processes."""
    return trace.get_tracer(name)