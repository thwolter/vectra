from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1 import ROUTERS
from app.core.config import get_settings
from app.core.dependencies import get_database_manager
from app.core.logging import configure_logging

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
    await db.initialize()
    await db.ensure_schema()
    try:
        yield
    finally:
        await db.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

for router, prefix in ROUTERS:
    app.include_router(router, prefix=prefix)


@app.get('/health', tags=['health'])
async def health_check():
    return {'status': 'ok'}


if settings.monitoring_enabled and settings.metrics_endpoint_enabled and generate_latest is not None:

    @app.get('/metrics', include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


FastAPIInstrumentor.instrument_app(app)
