"""
Rate Limiting Middleware

요청 속도 제한 (slowapi 기반)
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config import get_settings


logger = logging.getLogger("api-gateway.ratelimit")


# Rate Limiter 인스턴스 생성
limiter = Limiter(key_func=get_remote_address)


def get_limiter() -> Limiter:
    """Limiter 인스턴스 반환 (FastAPI 의존성 주입용)"""
    return limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limit 미들웨어

    IP 기반 요청 속도 제한:
    - 분당 요청 수 제한
    - 제한 초과 시 429 Too Many Requests 반환
    """

    def __init__(self, app, limit_per_minute: int = 100):
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Rate Limiting 비활성화 시 바로 통과
        if not self.settings.rate_limit_enabled:
            return await call_next(request)

        # 헬스 체크 엔드포인트는 제한하지 않음
        if request.url.path in ["/health", "/health/services", "/metrics"]:
            return await call_next(request)

        try:
            response = await call_next(request)
            return response
        except RateLimitExceeded:
            request_id = getattr(request.state, "request_id", "unknown")
            client_ip = get_remote_address(request)
            logger.warning(
                f"[{request_id}] Rate limit exceeded for IP: {client_ip}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
