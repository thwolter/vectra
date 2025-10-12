from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.v1 import ROUTERS
from app.core.config import get_settings
from app.core.dependencies import get_database_manager
from app.core.logging import configure_logging
from app.core.observability import get_tracer, init_otel_fastapi

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan hook to initialize database and ensure schema once.

    Uses DatabaseManager to initialize the async engine, ensure required
    extensions and create tables (dev/test convenience). In production,
    migrations should be responsible for schema, but this provides a
    safety net and satisfies test environment needs.
    """
    db = get_database_manager()

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(
        'app.startup',
        attributes={
            'service.name': settings.service_name_app,
            'service.namespace': settings.service_namespace,
            'deployment.environment': settings.deployment_env,
            'app.version': settings.version,
        },
    ) as span:
        span.add_event('startup.begin')
        logger.bind(
            component='app',
            service=settings.service_name_app,
            namespace=settings.service_namespace,
            env=settings.deployment_env,
            version=settings.version,
        ).info('APP_STARTUP: initialising database and validating schema')

        await db.initialize()
        await db.ensure_schema()
        span.add_event('startup.ready')

        # Dedicated, searchable startup log entry for Grafana/Loki or stdout
        logger.bind(
            component='app',
            service=settings.service_name_app,
            namespace=settings.service_namespace,
            env=settings.deployment_env,
            version=settings.version,
        ).info('APP_STARTED: application is ready to accept traffic')

    try:
        yield
    finally:
        await db.close()
        logger.bind(component='app').info('APP_SHUTDOWN: database connection closed')


app = FastAPI(title=settings.app_name, lifespan=lifespan)
init_otel_fastapi(
    app,
    service_name=settings.service_name_app,
    service_namespace=settings.service_namespace,
    deployment_environment=settings.deployment_env,
)

for router, prefix in ROUTERS:
    app.include_router(router, prefix=prefix)


@app.get('/health', tags=['health'], deprecated=True)
async def health_check():
    return {'status': 'ok'}


@app.get('/healthz', tags=['health'])
async def healthz():
    return {'status': 'ok'}


@app.get('/readyz', tags=['health'])
async def readyz():
    return {'status': 'ready'}
