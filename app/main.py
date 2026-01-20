from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.database import init_databases, close_databases
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.chat_room import router as chat_room_router
from app.api.message import router as message_router
from app.api.websocket import router as websocket_router
from app.api.friend import router as friend_router
from app.api.profile import router as profile_router
from app.api.user import router as user_router
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
# CSRF 미들웨어는 MVP에서 제거됨
from app.middleware.error_handler import ErrorHandlerMiddleware, create_http_exception_handler
from app.middleware.logging_middleware import LoggingMiddleware, PerformanceLoggingMiddleware
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware, XSSProtectionMiddleware, SQLInjectionProtectionMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()  # 로깅 시스템 초기화
    logger = get_logger(__name__)
    logger.info("Application startup initiated")

    await init_databases()
    logger.info("Databases initialized successfully")

    yield

    # Shutdown
    logger.info("Application shutdown initiated")
    await close_databases()
    logger.info("Application shutdown completed")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 미들웨어 등록 (순서가 중요 - 역순으로 실행됨)

# 에러 핸들러 미들웨어 (가장 먼저 등록)
app.add_middleware(ErrorHandlerMiddleware)

# 보안 헤더 미들웨어
app.add_middleware(SecurityHeadersMiddleware)

# XSS 방어 미들웨어
app.add_middleware(XSSProtectionMiddleware)

# SQL Injection 방어 미들웨어
app.add_middleware(SQLInjectionProtectionMiddleware)

# Rate Limiting 미들웨어
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_requests_per_minute,
    enabled=settings.rate_limit_enabled
)

# 성능 로깅 미들웨어
app.add_middleware(PerformanceLoggingMiddleware, slow_request_threshold_ms=1000)

# 요청/응답 로깅 미들웨어
app.add_middleware(LoggingMiddleware, log_requests=True, log_responses=not settings.debug)

# CSRF 보호 미들웨어는 MVP에서 제거됨

# HTTPException 핸들러 등록
app.add_exception_handler(HTTPException, create_http_exception_handler())

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_room_router)
app.include_router(message_router)
app.include_router(websocket_router)
app.include_router(friend_router)
app.include_router(profile_router)
app.include_router(user_router)

# 정적 파일 서빙 (업로드된 이미지들)
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
async def root():
    return {"message": "BigTech Chat Backend API"}


@app.get("/api/info")
async def api_info():
    """API 정보 조회"""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "description": "실시간 채팅 시스템 백엔드 API",
        "features": [
            "사용자 인증 및 프로필 관리",
            "실시간 채팅 (WebSocket)",
            "친구 관리 시스템",
            "프로필 이미지 업로드",
            "사용자 검색",
            "온라인 상태 관리"
        ]
    }
