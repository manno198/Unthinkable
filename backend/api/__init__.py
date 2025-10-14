"""API router configuration."""

from fastapi import APIRouter
from .ingest import router as ingest_router
from .query import router as query_router
from .text_documents import router as text_documents_router

router = APIRouter()

# Include sub-routers
router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
router.include_router(query_router, prefix="/query", tags=["query"])
router.include_router(text_documents_router, prefix="/text", tags=["text-documents"])
