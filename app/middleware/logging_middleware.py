"""
API 요청 로깅 미들웨어

모든 API 요청과 응답을 구조화된 형태로 로깅합니다.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger, set_request_context, clear_request_context, log_api_call

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """API 요청/응답 로깅 미들웨어"""

    def __init__(self, app, log_requests: bool = True, log_responses: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 요청 ID 생성
        request_id = str(uuid.uuid4())

        # 시작 시간 기록
        start_time = time.time()

        # 요청 컨텍스트 설정
        set_request_context(request_id)

        # 사용자 ID 추출 (가능한 경우)
        user_id = None
        try:
            # Authorization 헤더에서 사용자 정보 추출 시도
            if hasattr(request.state, 'user') and request.state.user:
                user_id = request.state.user.id
        except:
            pass

        # 요청 정보 로깅
        if self.log_requests:
            self._log_request(request, request_id, user_id)

        try:
            # 다음 미들웨어/엔드포인트 호출
            response = await call_next(request)

            # 응답 시간 계산
            duration_ms = (time.time() - start_time) * 1000

            # 응답 정보 로깅
            if self.log_responses:
                self._log_response(request, response, request_id, user_id, duration_ms)

            # API 호출 요약 로깅
            log_api_call(
                logger,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_id=user_id,
                request_id=request_id,
                query_params=dict(request.query_params) if request.query_params else None,
                user_agent=request.headers.get("user-agent"),
                client_ip=self._get_client_ip(request)
            )

            return response

        except Exception as e:
            # 예외 발생 시 로깅
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "event_type": "api_error",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "query_params": dict(request.query_params) if request.query_params else None,
                    "user_agent": request.headers.get("user-agent"),
                    "client_ip": self._get_client_ip(request)
                },
                exc_info=True
            )

            raise

        finally:
            # 요청 컨텍스트 정리
            clear_request_context()

    def _log_request(self, request: Request, request_id: str, user_id: int = None):
        """요청 정보 로깅"""

        # 민감한 헤더 필터링
        filtered_headers = {}
        sensitive_headers = {"authorization", "cookie", "x-api-key"}

        for name, value in request.headers.items():
            if name.lower() in sensitive_headers:
                filtered_headers[name] = "***REDACTED***"
            else:
                filtered_headers[name] = value

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "event_type": "request_started",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params) if request.query_params else None,
                "headers": filtered_headers,
                "user_id": user_id,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent")
            }
        )

    def _log_response(
        self,
        request: Request,
        response: Response,
        request_id: str,
        user_id: int,
        duration_ms: float
    ):
        """응답 정보 로깅"""

        # 응답 헤더 (민감한 정보 제외)
        filtered_headers = {}
        sensitive_headers = {"set-cookie"}

        for name, value in response.headers.items():
            if name.lower() in sensitive_headers:
                filtered_headers[name] = "***REDACTED***"
            else:
                filtered_headers[name] = value

        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "event_type": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "response_headers": filtered_headers,
                "user_id": user_id,
                "client_ip": self._get_client_ip(request)
            }
        )

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 사용 시)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # 첫 번째 IP가 실제 클라이언트 IP
            return forwarded_for.split(",")[0].strip()

        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 직접 연결인 경우
        if hasattr(request.client, "host"):
            return request.client.host

        return "unknown"


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """성능 로깅 미들웨어 (느린 요청 감지)"""

    def __init__(self, app, slow_request_threshold_ms: float = 1000):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        # 느린 요청 로깅
        if duration_ms > self.slow_request_threshold_ms:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path}",
                extra={
                    "event_type": "slow_request",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "threshold_ms": self.slow_request_threshold_ms,
                    "query_params": dict(request.query_params) if request.query_params else None,
                    "client_ip": self._get_client_ip(request)
                }
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        if hasattr(request.client, "host"):
            return request.client.host

        return "unknown"