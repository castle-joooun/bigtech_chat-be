"""
Friend Service - FastAPI Application Entry Point
=================================================

Friend Service는 친구 관계(Friendship)를 담당하는 독립적인 마이크로서비스입니다.

서비스 책임:
    - 친구 요청 전송/수락/거절/취소
    - 친구 목록 조회
    - 친구 관계 검색 (친구 추가용)
    - 사용자 차단/차단해제

포트: 8003
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.middleware import ErrorHandlerMiddleware
from app.core.logging import setup_logging, get_logger
from app.database import init_databases, close_databases
from app.kafka.producer import get_event_producer
from app.services.cache_service import init_friend_cache, close_friend_cache
from shared_lib.clients import init_user_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifecycle Manager

    Startup 순서:
        1. Logging 초기화
        2. Databases 초기화 (MySQL)
        3. Cache 서비스 초기화
        4. UserClient 초기화
        5. Kafka Producer 시작

    Shutdown 순서:
        1. Kafka Producer 종료
        2. Cache 서비스 종료
        3. Databases 종료
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
    await init_friend_cache()
    logger.info("Cache service initialized")

    # 4. UserClient 초기화 (user-service API 호출용)
    user_service_url = getattr(settings, 'user_service_url', 'http://localhost:8005')
    init_user_client(base_url=user_service_url)
    logger.info(f"UserClient initialized (user-service: {user_service_url})")

    # 5. Kafka Producer 시작
    producer = get_event_producer()
    await producer.start()
    logger.info("Kafka Producer started successfully")

    yield

    # =========================================================================
    # SHUTDOWN PHASE
    # =========================================================================
    logger.info("Application shutdown initiated")

    # 1. Kafka Producer 종료
    await producer.stop()
    logger.info("Kafka Producer stopped")

    # 2. Cache 서비스 종료
    await close_friend_cache()
    logger.info("Cache service closed")

    # 3. Databases 종료
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
    redoc_url="/redoc"
)

# =============================================================================
# Middleware 설정
# 등록 순서: 마지막에 등록된 미들웨어가 가장 먼저 실행됨
# 실행 순서: Error Handler → CORS → Router
# Note: XSS, SQL Injection 보안은 AWS WAF에서 처리
# =============================================================================

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
from app.api import friend

app.include_router(friend.router)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
