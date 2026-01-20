"""
Rate Limiting 미들웨어

Redis를 사용한 API Rate Limiting 구현
"""

import time
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger, log_security_event
from app.database.redis import check_rate_limit

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limiting 미들웨어

    IP 주소 기반으로 요청 제한을 적용합니다.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = None,
        burst_limit: int = None,
        enabled: bool = None
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.rate_limit_requests_per_minute
        self.burst_limit = burst_limit or settings.rate_limit_burst
        self.enabled = enabled if enabled is not None else settings.rate_limit_enabled

        # 예외 경로 (Rate Limiting 적용 안함)
        self.excluded_paths = {
            "/health",
            "/health/live",
            "/health/ready",
            "/docs",
            "/redoc",
            "/openapi.json"
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # 예외 경로 확인
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # 클라이언트 식별자 생성
        client_identifier = self._get_client_identifier(request)

        try:
            # Rate Limit 확인
            allowed, current_count, reset_time = await check_rate_limit(
                identifier=client_identifier,
                limit=self.requests_per_minute,
                window=60  # 1분
            )

            if not allowed:
                # Rate Limit 초과 시 보안 이벤트 로깅
                await self._log_rate_limit_exceeded(request, client_identifier, current_count)

                # Rate Limit 헤더 추가
                response = Response(
                    content='{"error": "rate_limit_exceeded", "message": "Too many requests"}',
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    media_type="application/json"
                )

                self._add_rate_limit_headers(response, current_count, reset_time)
                return response

            # 정상 요청 처리
            response = await call_next(request)

            # Rate Limit 헤더 추가
            self._add_rate_limit_headers(response, current_count, reset_time)

            return response

        except Exception as e:
            logger.error(f"Rate limiting error for {client_identifier}: {e}")
            # 에러 시 요청 허용 (fail-open)
            return await call_next(request)

    def _get_client_identifier(self, request: Request) -> str:
        """클라이언트 식별자 생성"""

        # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 사용 시)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # 첫 번째 IP가 실제 클라이언트 IP
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            # X-Real-IP 헤더 확인
            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                client_ip = real_ip
            else:
                # 직접 연결인 경우
                client_ip = getattr(request.client, "host", "unknown")

        # API 엔드포인트별로 다른 제한 적용 가능
        endpoint = request.url.path
        method = request.method

        # 기본 식별자: IP 주소
        return f"rate_limit:{client_ip}"

    def _add_rate_limit_headers(self, response: Response, current_count: int, reset_time: int):
        """Rate Limit 헤더 추가"""
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.requests_per_minute - current_count))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + reset_time)

    async def _log_rate_limit_exceeded(self, request: Request, identifier: str, count: int):
        """Rate Limit 초과 로깅"""
        client_ip = self._get_client_ip(request)

        log_security_event(
            logger,
            "rate_limit_exceeded",
            severity="medium",
            ip_address=client_ip,
            identifier=identifier,
            request_count=count,
            limit=self.requests_per_minute,
            path=request.url.path,
            method=request.method,
            user_agent=request.headers.get("user-agent")
        )

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return getattr(request.client, "host", "unknown")


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    고급 Rate Limiting 미들웨어

    사용자별, 엔드포인트별 다른 제한 적용
    """

    def __init__(self, app):
        super().__init__(app)

        # 엔드포인트별 제한 설정
        self.endpoint_limits = {
            # 인증 관련 - 더 엄격한 제한
            "/api/auth/login": {"requests": 5, "window": 60},
            "/api/auth/register": {"requests": 3, "window": 60},
            "/api/auth/forgot-password": {"requests": 3, "window": 300},

            # 메시지 관련 - 일반적인 제한
            "/api/messages": {"requests": 30, "window": 60},

            # 파일 업로드 - 낮은 제한
            "/api/messages/upload-image": {"requests": 10, "window": 60},
            "/api/profile/upload-image": {"requests": 5, "window": 60},

            # 검색 - 중간 제한
            "/api/messages/search": {"requests": 20, "window": 60},
            "/api/users/search": {"requests": 15, "window": 60},
        }

        # 사용자 역할별 제한 (향후 확장용)
        self.user_role_limits = {
            "premium": {"multiplier": 2.0},
            "admin": {"multiplier": 10.0},
            "basic": {"multiplier": 1.0}
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # 기본 제한 적용
        endpoint = self._normalize_endpoint(request.url.path)
        limit_config = self.endpoint_limits.get(endpoint)

        if limit_config:
            client_identifier = self._get_client_identifier(request, endpoint)

            try:
                allowed, current_count, reset_time = await check_rate_limit(
                    identifier=client_identifier,
                    limit=limit_config["requests"],
                    window=limit_config["window"]
                )

                if not allowed:
                    logger.warning(
                        f"Rate limit exceeded for {endpoint}",
                        extra={
                            "client_identifier": client_identifier,
                            "current_count": current_count,
                            "limit": limit_config["requests"],
                            "window": limit_config["window"]
                        }
                    )

                    response = Response(
                        content='{"error": "rate_limit_exceeded", "message": "Too many requests for this endpoint"}',
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        media_type="application/json"
                    )

                    response.headers["X-RateLimit-Limit"] = str(limit_config["requests"])
                    response.headers["X-RateLimit-Remaining"] = "0"
                    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + reset_time)
                    response.headers["X-RateLimit-Scope"] = endpoint

                    return response

            except Exception as e:
                logger.error(f"Advanced rate limiting error: {e}")

        return await call_next(request)

    def _normalize_endpoint(self, path: str) -> str:
        """엔드포인트 정규화 (경로 매개변수 제거)"""
        # '/api/messages/123' -> '/api/messages'
        # '/api/users/456/profile' -> '/api/users/profile'

        parts = path.split("/")
        normalized_parts = []

        for part in parts:
            # 숫자로만 이루어진 부분은 ID로 간주하고 제거
            if part.isdigit():
                continue
            # UUID 패턴도 제거 가능 (향후 확장)
            normalized_parts.append(part)

        return "/".join(normalized_parts)

    def _get_client_identifier(self, request: Request, endpoint: str) -> str:
        """클라이언트 식별자 생성 (엔드포인트별)"""
        client_ip = self._get_client_ip(request)

        # 인증된 사용자가 있는 경우 사용자 ID 사용
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user_rate_limit:{endpoint}:{user_id}"
        else:
            return f"ip_rate_limit:{endpoint}:{client_ip}"

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return getattr(request.client, "host", "unknown")


# =============================================================================
# Rate Limiting 데코레이터 (개별 엔드포인트용)
# =============================================================================

def rate_limit(requests: int, window: int = 60):
    """
    개별 엔드포인트용 Rate Limiting 데코레이터

    Args:
        requests: 허용 요청 수
        window: 시간 윈도우 (초)
    """

    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            if not settings.rate_limit_enabled:
                return await func(request, *args, **kwargs)

            client_ip = _get_client_ip_from_request(request)
            identifier = f"endpoint_rate_limit:{func.__name__}:{client_ip}"

            try:
                allowed, current_count, reset_time = await check_rate_limit(
                    identifier=identifier,
                    limit=requests,
                    window=window
                )

                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "rate_limit_exceeded",
                            "message": f"Too many requests. Limit: {requests} per {window} seconds",
                            "retry_after": reset_time
                        }
                    )

                return await func(request, *args, **kwargs)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Rate limiting decorator error: {e}")
                return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def _get_client_ip_from_request(request: Request) -> str:
    """요청에서 클라이언트 IP 추출"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    return getattr(request.client, "host", "unknown")