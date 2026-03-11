"""
User Service - FastAPI Application Entry Point
===============================================

User Service는 사용자 도메인을 담당하는 독립적인 마이크로서비스입니다.

서비스 책임:
    - 사용자 인증 (회원가입, 로그인, 로그아웃)
    - 사용자 프로필 관리
    - 온라인 상태 관리 (Redis 기반)
    - 사용자 검색

포트: 8001
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.middleware import (
    ErrorHandlerMiddleware,
    OnlineStatusMiddleware
)
from app.core.logging import setup_logging, get_logger
from app.api import auth, profile, user
from app.database import init_databases, close_databases
from app.kafka.producer import get_event_producer
from app.services.heartbeat_monitor import get_heartbeat_monitor
from app.services.cache_service import init_user_cache, close_user_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifecycle Manager

    Startup 순서:
        1. Logging 초기화
        2. Databases 초기화 (MySQL → Redis)
        3. Cache 서비스 초기화
        4. Kafka Producer 시작
        5. Heartbeat Monitor 시작

    Shutdown 순서:
        1. Heartbeat Monitor 중지
        2. Kafka Producer 종료
        3. Cache 서비스 종료
        4. Databases 종료
    """
    # =========================================================================
    # STARTUP PHASE
    # =========================================================================

    # 1. Logging 초기화
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Application startup initiated")

    # 2. Databases 초기화
    await init_databases()
    logger.info("Databases initialized successfully")

    # 3. Cache 서비스 초기화
    await init_user_cache()
    logger.info("Cache service initialized")

    # 4. Kafka Producer 시작
    producer = get_event_producer()
    await producer.start()
    logger.info("Kafka Producer started successfully")

    # 5. Heartbeat Monitor 시작
    heartbeat_monitor = get_heartbeat_monitor()
    await heartbeat_monitor.start()
    logger.info("Heartbeat monitor started")

    yield

    # =========================================================================
    # SHUTDOWN PHASE
    # =========================================================================
    logger.info("Application shutdown initiated")

    # 1. Heartbeat Monitor 중지
    await heartbeat_monitor.stop()
    logger.info("Heartbeat monitor stopped")

    # 2. Kafka Producer 종료
    await producer.stop()
    logger.info("Kafka Producer stopped")

    # 3. Cache 서비스 종료
    await close_user_cache()
    logger.info("Cache service closed")

    # 4. Databases 종료
    await close_databases()
    logger.info("Application shutdown completed")


# =============================================================================
# FastAPI Application Instance
# =============================================================================
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# =============================================================================
# Middleware 설정
# 등록 순서: 마지막에 등록된 미들웨어가 가장 먼저 실행됨
# 실행 순서: Error Handler → CORS → Online Status → Router
# Note: XSS, SQL Injection 보안은 AWS WAF에서 처리
# =============================================================================

# 3. Online Status (user-service 전용) - 가장 안쪽에서 실행
app.add_middleware(OnlineStatusMiddleware)

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Error Handler (가장 바깥 - 모든 예외를 캐치)
app.add_middleware(ErrorHandlerMiddleware)

# =============================================================================
# Router 등록
# =============================================================================
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(user.router)

# =============================================================================
# Observability 설정
# =============================================================================
Instrumentator().instrument(app).expose(app)


# =============================================================================
# Health Check Endpoints
# =============================================================================
@app.get("/")
async def root():
    """서비스 정보 엔드포인트"""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health Check 엔드포인트"""
    return {
        "status": "healthy",
        "service": settings.app_name
    }


# =============================================================================
# 직접 실행 시 (개발 환경)
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
