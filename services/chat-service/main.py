"""
Chat Service - FastAPI Application

채팅방 관리, 메시지 전송/조회, 실시간 메시지 스트리밍을 담당하는 마이크로서비스
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.config import settings
from app.database.mongodb import init_mongodb, close_mongodb
from app.database.redis import init_redis, close_redis
from app.kafka.producer import get_event_producer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    print(f"🚀 {settings.app_name} starting up...")

    # MongoDB 초기화
    await init_mongodb()

    # Redis 초기화
    await init_redis()

    # Initialize Kafka Producer
    producer = get_event_producer()
    await producer.start()

    yield

    # Shutdown
    print(f"🛑 {settings.app_name} shutting down...")

    # Close MongoDB connection
    await close_mongodb()

    # Close Redis connection
    await close_redis()

    # Stop Kafka Producer
    await producer.stop()


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
from app.api import chat_room, message

app.include_router(chat_room.router)
app.include_router(message.router)

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
