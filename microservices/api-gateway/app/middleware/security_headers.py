"""
Security Headers Middleware

보안 관련 HTTP 헤더 추가
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    보안 헤더 미들웨어

    OWASP 권장 보안 헤더 추가:
    - X-Content-Type-Options: MIME 타입 스니핑 방지
    - X-Frame-Options: Clickjacking 방지
    - X-XSS-Protection: 브라우저 XSS 필터 활성화
    - Content-Security-Policy: 컨텐츠 보안 정책
    - Strict-Transport-Security: HTTPS 강제
    - Referrer-Policy: 리퍼러 정보 제어
    - Permissions-Policy: 브라우저 기능 제한
    """

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 보안 헤더 추가
        for header_name, header_value in self.SECURITY_HEADERS.items():
            response.headers[header_name] = header_value

        return response
