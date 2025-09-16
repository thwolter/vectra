from .document_routes import router as document_router
from .job_routes import router as job_router
from .profile_routes import router as profile_router
from .retrieval_routes import router as retrieval_router
from .streaming_routes import streaming_router
from .upload_routes import router as upload_router

ROUTERS = [
    (upload_router, '/api'),
    (profile_router, '/api'),
    (streaming_router, '/api'),
    (retrieval_router, '/api'),
    (job_router, '/api'),
    (document_router, '/api'),
]
