from .document_routes import router as document_router
from .job_routes import router as job_router
from .search_routes import router as search_router
from .streaming_routes import streaming_router
from .upload_routes import router as upload_router

ROUTERS = [
    (upload_router, '/api'),
    (streaming_router, '/api'),
    (job_router, '/api'),
    (document_router, '/api'),
    (search_router, '/api'),
]
