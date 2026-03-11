"""
SQL Injection Protection Middleware

SQL Injection 공격 방어 (Pure ASGI)
"""
import re
import json
import logging
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import get_settings


logger = logging.getLogger("api-gateway.security")


class SQLInjectionProtectionMiddleware:
    """
    SQL Injection 방어 미들웨어 (Pure ASGI)

    요청 파라미터에서 SQL Injection 패턴 탐지:
    - SQL 키워드 (UNION, SELECT, INSERT, DELETE, DROP 등)
    - 주석 패턴 (--, /*, */)
    - 따옴표와 세미콜론 조합
    - 시스템 프로시저 (xp_, sp_)
    """

    # 위험 문자/패턴 (legacy 코드에서 가져옴)
    DANGEROUS_CHARS = ["--", "/*", "*/", "xp_", "sp_"]

    # SQL Injection 패턴 정규식
    SQL_PATTERNS = [
        re.compile(r"\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", re.IGNORECASE),
        re.compile(r"\b(OR|AND)\s+[\d'\"=]+\s*[=<>]", re.IGNORECASE),  # OR 1=1, AND '1'='1'
        re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP)", re.IGNORECASE),  # 다중 쿼리
        re.compile(r"--\s*$", re.MULTILINE),  # SQL 주석
        re.compile(r"/\*.*?\*/", re.DOTALL),  # 블록 주석
        re.compile(r"\bEXEC\s*\(", re.IGNORECASE),  # EXEC()
        re.compile(r"\bSLEEP\s*\(", re.IGNORECASE),  # SLEEP() - 시간 기반 공격
        re.compile(r"\bBENCHMARK\s*\(", re.IGNORECASE),  # BENCHMARK()
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
        if not self.settings.sql_injection_protection_enabled:
            await self.app(scope, receive, send)
            return

        # 제외 경로 확인
        path = scope.get("path", "")
        if path in self.EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        # 쿼리 파라미터 검사
        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string and self._detect_sql_injection(query_string):
            await self._send_block_response(scope, send, "SQL injection detected in query params")
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
                        if self._detect_sql_injection(body_str):
                            await self._send_block_response(scope, send, "SQL injection detected in body")
                            return
                    except Exception:
                        pass

        await self.app(scope, receive, send)

    def _detect_sql_injection(self, value: str) -> bool:
        """SQL Injection 패턴 탐지"""
        if not value:
            return False

        # 위험 문자 검사
        for char in self.DANGEROUS_CHARS:
            if char in value:
                return True

        # SQL 패턴 검사
        for pattern in self.SQL_PATTERNS:
            if pattern.search(value):
                return True

        return False

    async def _send_block_response(self, scope: Scope, send: Send, reason: str):
        """요청 차단 응답"""
        request_id = scope.get("state", {}).get("request_id", "unknown")
        logger.warning(f"[{request_id}] SQL injection attack blocked: {reason}")

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
