from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from loguru import logger
from nexor.health import install_health_routes
from nexor.logging import configure_loguru_logging
from nexor.observability import get_tracer, init_otel_fastapi
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from api.v1 import ROUTERS
from core.config import get_settings
from core.db import test_db_connection
from core.logging import build_log_export_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hook.

    - Verifies database connectivity at startup.
    - Emits a short startup span with basic service metadata.
    """

    # Ensure DB connectivity before accepting traffic
    await test_db_connection()
    logger.info('DB_READY: database is ready to accept connections')

    # Settings attached directly on the app (set in create_app)
    settings = get_settings()

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(
        'src.startup',
        attributes={
            'service.name': settings.service_name_app,
            'service.namespace': settings.service_namespace,
            'deployment.environment': settings.deployment_env,
            'src.version': settings.version,
        },
    ) as span:
        span.add_event('startup.begin')
        span.add_event('startup.ready')
        logger.info('APP_STARTED: application is ready to accept traffic')

    yield


def create_app() -> FastAPI:
    """Application factory.

    Builds the FastAPI app with:
    - settings loaded once
    - structured logging configured
    - CORS middleware
    - OpenTelemetry integration
    - API routers and health routes
    """

    settings = get_settings()

    # Configure Loguru and OTLP export once per process
    configure_loguru_logging(
        settings=settings,
        exporter_settings=build_log_export_settings(
            settings,
            service_name=getattr(settings, 'service_name_app', None),
        ),
    )

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allow_origins),
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        ),
    ]

    logger.info(f'CORS origins: {settings.cors_allow_origins}')

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        middleware=middleware,
    )

    # Observability wiring (tracing/metrics)
    init_otel_fastapi(
        app,
        service_name=settings.service_name_app,
        service_namespace=settings.service_namespace,
        deployment_environment=settings.deployment_env,
    )

    # Register versioned API routers
    for router, prefix in ROUTERS:
        app.include_router(router, prefix=prefix)

    # Health and readiness routes from nexor.health
    install_health_routes(app, settings=settings)

    return app


# Default ASGI application for uvicorn/gunicorn
app = create_app()
