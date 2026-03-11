"""
Friend Service Middleware Package
==================================

에러 처리를 위한 미들웨어 모듈입니다.
Note: XSS, SQL Injection 보안은 AWS WAF에서 처리합니다.
"""

from app.middleware.error_handler import ErrorHandlerMiddleware

__all__ = [
    "ErrorHandlerMiddleware"
]
