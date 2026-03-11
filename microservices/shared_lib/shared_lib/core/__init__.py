"""
Core Module (핵심 모듈)
=====================

에러 처리, 검증, 설정 관련 공통 코드를 제공합니다.
"""

from .errors import (
    # Response Models
    ErrorResponse,
    ValidationError,
    ValidationErrorResponse,
    # Exceptions
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

from .validators import (
    Validator,
    validate_user_registration,
    validate_user_login,
)

from .config import BaseServiceSettings

__all__ = [
    # Errors
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
    # Validators
    "Validator",
    "validate_user_registration",
    "validate_user_login",
    # Config
    "BaseServiceSettings",
]
