"""
Friend Service - FastAPI Application

친구 관계 관리를 담당하는 마이크로서비스
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    print(f"🚀 {settings.app_name} starting up...")

    # Database connections are initialized lazily on first request

    # TODO: Initialize Kafka Producer

    yield

    # Shutdown
    print(f"🛑 {settings.app_name} shutting down...")

    # TODO: Stop Kafka Producer


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.api import friend

app.include_router(friend.router)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
