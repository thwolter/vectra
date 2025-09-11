from .upload_routes import router as upload_router
from .job_routes import router as job_router
from .profile_routes import router as profile_router
from .document_routes import router as document_router

ROUTERS = [
    (upload_router, '/api'),
    (profile_router, '/api'),
    (document_router, '/api'),
    (job_router, '/api'),
]
