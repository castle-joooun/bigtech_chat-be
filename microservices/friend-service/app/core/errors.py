"""
Error Handling Module (에러 처리 모듈)
=====================================

이 모듈은 shared_lib.core.errors를 re-export합니다.
기존 코드와의 호환성을 위해 유지됩니다.
"""

from shared_lib.core.errors import (
    # Response Models
    ErrorResponse,
    ValidationError,
    ValidationErrorResponse,
    # Exception Classes
    BaseCustomException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    ResourceNotFoundException,
    ConflictException,
    BusinessLogicException,
    ExternalServiceException,
    RateLimitException,
    # Helper Functions
    create_error_response,
    create_validation_error_response,
    # Factory Functions
    user_not_found_error,
    invalid_credentials_error,
    email_already_exists_error,
    username_already_exists_error,
    invalid_token_error,
    password_validation_error,
)

__all__ = [
    "ErrorResponse",
    "ValidationError",
    "ValidationErrorResponse",
    "BaseCustomException",
    "ValidationException",
    "AuthenticationException",
    "AuthorizationException",
    "ResourceNotFoundException",
    "ConflictException",
    "BusinessLogicException",
    "ExternalServiceException",
    "RateLimitException",
    "create_error_response",
    "create_validation_error_response",
    "user_not_found_error",
    "invalid_credentials_error",
    "email_already_exists_error",
    "username_already_exists_error",
    "invalid_token_error",
    "password_validation_error",
]
