"""
Request Logging Middleware

요청/응답 로깅
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("api-gateway")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    요청 로깅 미들웨어

    - 요청 시작/완료 시간 기록
    - 응답 시간 계산
    - 상태 코드, 경로, 메서드 로깅
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # Request ID 가져오기 (RequestIDMiddleware에서 설정)
        request_id = getattr(request.state, "request_id", "unknown")

        # 요청 로깅
        logger.info(
            f"[{request_id}] --> {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        # 다음 미들웨어/핸들러 호출
        response = await call_next(request)

        # 응답 시간 계산
        process_time = time.time() - start_time
        process_time_ms = round(process_time * 1000, 2)

        # 응답 로깅
        logger.info(
            f"[{request_id}] <-- {request.method} {request.url.path} "
            f"completed with {response.status_code} in {process_time_ms}ms"
        )

        # 응답 헤더에 처리 시간 추가
        response.headers["X-Process-Time"] = str(process_time_ms)

        return response
