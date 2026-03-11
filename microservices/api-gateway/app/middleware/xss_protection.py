"""
XSS Protection Middleware

Cross-Site Scripting 공격 방어 (Pure ASGI)
"""
import re
import json
import logging
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import get_settings


logger = logging.getLogger("api-gateway.security")


class XSSProtectionMiddleware:
    """
    XSS 방어 미들웨어 (Pure ASGI)

    요청 파라미터와 바디에서 XSS 패턴 탐지:
    - <script> 태그
    - javascript: 프로토콜
    - 이벤트 핸들러 (onclick, onerror 등)
    - 제어 문자
    """

    # XSS 패턴 정규식
    XSS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick=, onerror= 등
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
        re.compile(r'<link[^>]*>', re.IGNORECASE),
        re.compile(r'<meta[^>]*>', re.IGNORECASE),
        re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]'),  # 제어 문자
    ]

    # 검사 제외 경로
    EXCLUDED_PATHS = ["/health", "/health/services", "/metrics"]

    def __init__(self, app: ASGIApp):
        self.app = app
        self.settings = get_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 보호 비활성화 시 바로 통과
        if not self.settings.xss_protection_enabled:
            await self.app(scope, receive, send)
            return

        # 제외 경로 확인
        path = scope.get("path", "")
        if path in self.EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        # 쿼리 파라미터 검사
        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string and self._detect_xss(query_string):
            await self._send_block_response(scope, send, "XSS detected in query params")
            return

        # POST/PUT/PATCH 요청의 바디 검사
        method = scope.get("method", "GET")
        if method in ["POST", "PUT", "PATCH"]:
            # 캐싱된 body 확인 (BodyCacheMiddleware에서 설정)
            cached_body = scope.get("_cached_body")
            if cached_body:
                # Content-Type 확인
                headers = dict(scope.get("headers", []))
                content_type = headers.get(b"content-type", b"").decode("utf-8")

                if "application/json" in content_type:
                    try:
                        body_str = cached_body.decode("utf-8")
                        if self._detect_xss(body_str):
                            await self._send_block_response(scope, send, "XSS detected in body")
                            return
                    except Exception:
                        pass

        await self.app(scope, receive, send)

    def _detect_xss(self, value: str) -> bool:
        """XSS 패턴 탐지"""
        if not value:
            return False

        for pattern in self.XSS_PATTERNS:
            if pattern.search(value):
                return True
        return False

    async def _send_block_response(self, scope: Scope, send: Send, reason: str):
        """요청 차단 응답"""
        request_id = scope.get("state", {}).get("request_id", "unknown")
        logger.warning(f"[{request_id}] XSS attack blocked: {reason}")

        response_body = json.dumps({
            "error": "invalid_request",
            "message": "Request contains potentially dangerous content"
        }).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 400,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(response_body)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": response_body,
        })
