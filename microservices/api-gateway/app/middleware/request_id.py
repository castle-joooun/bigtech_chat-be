"""
Request ID Middleware

분산 추적을 위한 X-Request-ID 생성 및 전파
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Request ID 미들웨어

    - 요청에 X-Request-ID가 없으면 새로 생성
    - 응답에 X-Request-ID 헤더 추가
    - request.state.request_id로 접근 가능
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 기존 요청 ID 사용 또는 새로 생성
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())

        # request.state에 저장 (다른 미들웨어/핸들러에서 접근 가능)
        request.state.request_id = request_id

        # 다음 미들웨어/핸들러 호출
        response = await call_next(request)

        # 응답 헤더에 Request ID 추가
        response.headers[REQUEST_ID_HEADER] = request_id

        return response
