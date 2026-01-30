"""
보안 미들웨어

XSS 방어, CSRF 방어, 보안 헤더 설정 등을 포함합니다.
"""

import re
import html
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger, log_security_event

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    보안 헤더 설정 미들웨어

    XSS, Clickjacking, MIME 스니핑 등의 공격을 방어하는 헤더를 추가합니다.
    """

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # XSS 방어 헤더
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 콘텐츠 타입 스니핑 방지
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 클릭재킹 방지
        response.headers["X-Frame-Options"] = "DENY"

        # HSTS (HTTPS 강제)
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        csp_policy = self._build_csp_policy()
        response.headers["Content-Security-Policy"] = csp_policy

        # 추천인 정책
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 권한 정책
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response

    def _build_csp_policy(self) -> str:
        """Content Security Policy 구성"""
        if settings.debug:
            # 개발 환경: 더 관대한 정책 (Swagger UI CDN 허용)
            return (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: blob: https://fastapi.tiangolo.com; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self' ws: wss:; "
                "media-src 'self'; "
                "object-src 'none'; "
                "frame-ancestors 'none';"
            )
        else:
            # 프로덕션 환경: 엄격한 정책
            return (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self' wss:; "
                "media-src 'self'; "
                "object-src 'none'; "
                "frame-ancestors 'none'; "
                "upgrade-insecure-requests;"
            )


class XSSProtectionMiddleware(BaseHTTPMiddleware):
    """
    XSS 공격 방어 미들웨어

    요청 데이터에서 악성 스크립트를 탐지하고 차단합니다.
    """

    def __init__(self, app):
        super().__init__(app)

        # XSS 패턴들
        self.xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'<link[^>]*>',
            r'<meta[^>]*>',
            r'expression\s*\(',
            r'@import',
            r'vbscript:',
            r'<svg[^>]*>.*?</svg>',
        ]

        # 컴파일된 정규식
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in self.xss_patterns
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # POST, PUT, PATCH 요청의 body 검사
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # 요청 body 읽기
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8')

                    # XSS 패턴 검사
                    if self._contains_xss(body_str):
                        await self._log_xss_attempt(request, body_str)

                        return Response(
                            content='{"error": "xss_detected", "message": "Potentially malicious content detected"}',
                            status_code=400,
                            media_type="application/json"
                        )

                    # 요청 body를 다시 설정 (FastAPI가 다시 읽을 수 있도록)
                    request._body = body

            except Exception as e:
                logger.error(f"XSS protection error: {e}")

        # URL 파라미터 검사
        for param_name, param_value in request.query_params.items():
            if self._contains_xss(param_value):
                await self._log_xss_attempt(request, f"Query param {param_name}: {param_value}")

                return Response(
                    content='{"error": "xss_detected", "message": "Potentially malicious content in parameters"}',
                    status_code=400,
                    media_type="application/json"
                )

        return await call_next(request)

    def _contains_xss(self, content: str) -> bool:
        """XSS 패턴 포함 여부 확인"""
        if not content:
            return False

        # HTML 디코딩 후 검사
        decoded_content = html.unescape(content)

        for pattern in self.compiled_patterns:
            if pattern.search(decoded_content):
                return True

        return False

    async def _log_xss_attempt(self, request: Request, content: str):
        """XSS 시도 로깅"""
        client_ip = self._get_client_ip(request)

        log_security_event(
            logger,
            "xss_attempt",
            severity="high",
            ip_address=client_ip,
            path=request.url.path,
            method=request.method,
            user_agent=request.headers.get("user-agent"),
            content_sample=content[:200],  # 처음 200자만 로깅
            content_length=len(content)
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


class SQLInjectionProtectionMiddleware(BaseHTTPMiddleware):
    """
    SQL Injection 공격 방어 미들웨어

    요청 데이터에서 SQL Injection 패턴을 탐지하고 차단합니다.
    """

    def __init__(self, app):
        super().__init__(app)

        # SQL Injection 패턴들
        self.sql_patterns = [
            r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b',
            r'(\bor\b|\band\b)(\s+\d+\s*=\s*\d+|\s+\'[^\']*\'\s*=\s*\'[^\']*\')',
            r'\';\s*(drop|delete|update|insert)',
            r'--.*$',
            r'/\*.*?\*/',
            r'\bxp_\w+',
            r'\bsp_\w+',
            r'(\bor\b|\band\b)\s+\d+\s*=\s*\d+',
            r'\'.*(\bor\b|\band\b).*\'',
            r'\bhaving\b.*\bcount\b.*\*',
            r'\bgroup_concat\b',
            r'\binformation_schema\b',
            r'\bsys\.\w+',
        ]

        # 컴파일된 정규식
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.sql_patterns
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # GET 파라미터 검사
        for param_name, param_value in request.query_params.items():
            if self._contains_sql_injection(param_value):
                await self._log_sql_injection_attempt(request, f"Query param {param_name}: {param_value}")

                return Response(
                    content='{"error": "sql_injection_detected", "message": "Potentially malicious SQL detected"}',
                    status_code=400,
                    media_type="application/json"
                )

        # POST 데이터 검사
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8')

                    # JSON 데이터인 경우 값들 검사
                    try:
                        json_data = json.loads(body_str)
                        if self._check_json_for_sql_injection(json_data):
                            await self._log_sql_injection_attempt(request, "JSON body")

                            return Response(
                                content='{"error": "sql_injection_detected", "message": "Potentially malicious SQL in request body"}',
                                status_code=400,
                                media_type="application/json"
                            )
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 전체 문자열 검사
                        if self._contains_sql_injection(body_str):
                            await self._log_sql_injection_attempt(request, "Request body")

                            return Response(
                                content='{"error": "sql_injection_detected", "message": "Potentially malicious SQL in request body"}',
                                status_code=400,
                                media_type="application/json"
                            )

                    # 요청 body를 다시 설정
                    request._body = body

            except Exception as e:
                logger.error(f"SQL injection protection error: {e}")

        return await call_next(request)

    def _contains_sql_injection(self, content: str) -> bool:
        """SQL Injection 패턴 포함 여부 확인"""
        if not content:
            return False

        for pattern in self.compiled_patterns:
            if pattern.search(content):
                return True

        return False

    def _check_json_for_sql_injection(self, data) -> bool:
        """JSON 데이터에서 SQL Injection 패턴 확인"""
        if isinstance(data, dict):
            for value in data.values():
                if self._check_json_for_sql_injection(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._check_json_for_sql_injection(item):
                    return True
        elif isinstance(data, str):
            return self._contains_sql_injection(data)

        return False

    async def _log_sql_injection_attempt(self, request: Request, location: str):
        """SQL Injection 시도 로깅"""
        client_ip = self._get_client_ip(request)

        log_security_event(
            logger,
            "sql_injection_attempt",
            severity="high",
            ip_address=client_ip,
            path=request.url.path,
            method=request.method,
            user_agent=request.headers.get("user-agent"),
            location=location
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


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF 공격 방어 미들웨어 (기본 구현)

    실제 프로덕션에서는 더 정교한 CSRF 토큰 시스템이 필요합니다.
    """

    def __init__(self, app):
        super().__init__(app)

        # CSRF 보호가 필요한 메소드
        self.protected_methods = {"POST", "PUT", "PATCH", "DELETE"}

        # CSRF 보호 예외 경로
        self.excluded_paths = {
            "/api/auth/login",
            "/api/auth/register",
            "/health",
            "/docs",
            "/redoc"
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in self.protected_methods and request.url.path not in self.excluded_paths:
            # Origin 헤더 확인
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")

            if not origin and not referer:
                logger.warning(f"CSRF: Missing origin/referer header for {request.url.path}")

            # 개발 환경에서는 CSRF 검사 완화
            if not settings.debug:
                # 프로덕션에서는 더 엄격한 CSRF 검사 구현
                pass

        return await call_next(request)


# =============================================================================
# 통합 보안 미들웨어
# =============================================================================

class ComprehensiveSecurityMiddleware(BaseHTTPMiddleware):
    """
    통합 보안 미들웨어

    여러 보안 기능을 하나의 미들웨어로 통합
    """

    def __init__(self, app):
        super().__init__(app)
        self.security_headers = SecurityHeadersMiddleware(app)
        self.xss_protection = XSSProtectionMiddleware(app)
        self.sql_injection_protection = SQLInjectionProtectionMiddleware(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # SQL Injection 검사
        response = await self.sql_injection_protection.dispatch(request, call_next)
        if response.status_code == 400:
            return response

        # XSS 검사
        response = await self.xss_protection.dispatch(request, call_next)
        if response.status_code == 400:
            return response

        # 보안 헤더 추가
        response = await self.security_headers.dispatch(request, call_next)

        return response