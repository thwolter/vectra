from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from api.v1 import ROUTERS
from core.config import get_settings
from core.db import get_engine
from core.logging import configure_logging
from core.observability import get_tracer, init_otel_fastapi

settings = get_settings()
configure_logging()

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


async def test_db_connection() -> None:
    """Test database connectivity at startup.

    Raises:
        RuntimeError: if the database connection fails.
    """
    try:
        engine = get_engine()
        logger.info(engine.url.render_as_string(hide_password=False))
        async with engine.connect() as conn:
            pass
        logger.info('Database connection test successful')
    except Exception as exc:
        logger.exception('Database connection test failed')
        raise RuntimeError('Failed to connect to database') from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan hook to initialize database and ensure schema once.

    Uses DatabaseManager to initialize the async engine, ensure required
    extensions and create tables (dev/test convenience). In production,
    migrations should be responsible for schema, but this provides a
    safety net and satisfies test environment needs.
    """

    await test_db_connection()

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
        logger.bind(
            component='src',
            service=settings.service_name_app,
            namespace=settings.service_namespace,
            env=settings.deployment_env,
            version=settings.version,
        ).info('APP_STARTUP: initialising database and validating schema')

        span.add_event('startup.ready')

        # Dedicated, searchable startup log entry for Grafana/Loki or stdout
        logger.bind(
            component='src',
            service=settings.service_name_app,
            namespace=settings.service_namespace,
            env=settings.deployment_env,
            version=settings.version,
        ).info('APP_STARTED: application is ready to accept traffic')
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan, middleware=middleware, version=settings.version)

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
