from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes.auth import router as auth_router
from app.api.routes.repos import router as repos_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.docs import router as docs_router
from app.api.routes.security import router as security_router
from app.api.routes.search import router as search_router
from app.api.routes.export import router as export_router
from app.api.routes.webhooks import router as webhooks_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CodeDocs API...")
    yield
    logger.info("Shutting down...")

app = FastAPI(title="CodeDocs API", version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.allowed_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(repos_router, prefix="/api/repos", tags=["Repositories"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(docs_router, prefix="/api/docs", tags=["Documentation"])
app.include_router(security_router, prefix="/api/security", tags=["Security"])
app.include_router(search_router, prefix="/api/search", tags=["Search"])
app.include_router(export_router, prefix="/api/export", tags=["Export"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["Webhooks"])
