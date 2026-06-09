"""
Refinery Notification Intelligence Assistant — FastAPI Application

An AI-powered maintenance notification analytics backend that uses
a deterministic analytics engine (not LLM) as the source of truth
for all calculations.

Architecture:
  Upload → Schema Normalization → Analytics Engine → AI Intent → Response Generator
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import upload, chat
from app.routers import auth
from app.services.data_store import data_store

# ─── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🚀 Refinery Notification Intelligence Assistant starting up")
    logger.info(f"   AI Provider: {settings.AI_PROVIDER} ({settings.AI_MODEL})")
    logger.info(f"   CORS Origins: {settings.cors_origins_list}")
    logger.info(f"   Max Upload Size: {settings.MAX_UPLOAD_SIZE_MB}MB")
    yield
    # Cleanup on shutdown
    count = data_store.cleanup_expired()
    logger.info(f"🛑 Shutting down. Cleaned up {count} expired sessions.")


# ─── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Refinery Notification Intelligence Assistant",
    description=(
        "AI-powered refinery maintenance notification analytics backend. "
        "Upload SAP PM notification data and ask natural language questions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───────────────────────────────────────────────────────────────────

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(auth.router)


# ─── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Refinery Notification Intelligence Assistant",
        "version": "1.0.0",
        "ai_provider": settings.AI_PROVIDER,
        "ai_model": settings.AI_MODEL,
        "active_sessions": data_store.active_session_count,
    }
