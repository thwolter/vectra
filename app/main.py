from fastapi import FastAPI

from app.api.v1.upload_routes import router as upload_router
from app.api.v1.profile_routes import router as profile_router
from app.api.v1.document_routes import router as document_router
from app.api.v1.job_routes import router as job_router

from app.core.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(upload_router, prefix='/api')
app.include_router(profile_router, prefix='/api')
app.include_router(document_router, prefix='/api')
app.include_router(job_router, prefix='/api')


@app.get('/health', tags=['health'])
async def health_check():
    return {'status': 'ok'}
