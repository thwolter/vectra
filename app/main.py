from fastapi import FastAPI

from app.api.v1 import ROUTERS
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

for router, prefix in ROUTERS:
    app.include_router(router, prefix=prefix)


@app.get('/health', tags=['health'])
async def health_check():
    return {'status': 'ok'}
