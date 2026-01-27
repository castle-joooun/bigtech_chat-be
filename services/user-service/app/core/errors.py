from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """표준 에러 응답 모델"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    status_code: int


class ValidationError(BaseModel):
    """검증 에러 세부사항"""
    field: str
    message: str
    value: Optional[Any] = None


class ValidationErrorResponse(BaseModel):
    """검증 에러 응답 모델"""
    error: str = "validation_error"
    message: str
    validation_errors: List[ValidationError]
    status_code: int


# =============================================================================
# 커스텀 예외 클래스들
# =============================================================================

class BaseCustomException(HTTPException):
    """기본 커스텀 예외 클래스"""
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error = error
        self.message = message
        self.details = details
        self.status_code = status_code  # status_code를 먼저 설정
        super().__init__(status_code=status_code, detail=self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        """예외를 딕셔너리로 변환"""
        return {
            "error": self.error,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code
        }


class ValidationException(BaseCustomException):
    """입력 검증 실패 예외"""
    def __init__(
        self,
        message: str = "Validation failed",
        validation_errors: Optional[List[ValidationError]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.validation_errors = validation_errors or []
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="validation_error",
            message=message,
            details=details
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error,
            "message": self.message,
            "validation_errors": [error.model_dump() for error in self.validation_errors],
            "status_code": self.status_code
        }


class AuthenticationException(BaseCustomException):
    """인증 실패 예외"""
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="authentication_error",
            message=message,
            details=details
        )


class AuthorizationException(BaseCustomException):
    """권한 부족 예외"""
    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error="authorization_error",
            message=message,
            details=details
        )


class ResourceNotFoundException(BaseCustomException):
    """리소스를 찾을 수 없음 예외"""
    def __init__(
        self,
        resource: str = "Resource",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"{resource} not found"
        
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error="resource_not_found",
            message=message,
            details=details or {"resource": resource}
        )


class ConflictException(BaseCustomException):
    """리소스 충돌 예외"""
    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error="resource_conflict",
            message=message,
            details=details
        )


class BusinessLogicException(BaseCustomException):
    """비즈니스 로직 예외"""
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="business_logic_error",
            message=message,
            details=details
        )


class ExternalServiceException(BaseCustomException):
    """외부 서비스 에러 예외"""
    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error="external_service_error",
            message=f"{service}: {message}",
            details=details or {"service": service}
        )


class RateLimitException(BaseCustomException):
    """요청 제한 초과 예외"""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if retry_after:
            details = details or {}
            details["retry_after"] = retry_after
            
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error="rate_limit_exceeded",
            message=message,
            details=details
        )


# =============================================================================
# 에러 헬퍼 함수들
# =============================================================================

def create_error_response(
    error: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None
) -> ErrorResponse:
    """표준 에러 응답 생성"""
    return ErrorResponse(
        error=error,
        message=message,
        status_code=status_code,
        details=details
    )


def create_validation_error_response(
    message: str,
    validation_errors: List[ValidationError],
    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
) -> ValidationErrorResponse:
    """검증 에러 응답 생성"""
    return ValidationErrorResponse(
        message=message,
        validation_errors=validation_errors,
        status_code=status_code
    )


# =============================================================================
# 자주 사용되는 에러 팩토리 함수들
# =============================================================================

def user_not_found_error(user_id: Optional[int] = None):
    """사용자를 찾을 수 없음 에러"""
    details = {"user_id": user_id} if user_id else None
    return ResourceNotFoundException("User", details=details)


def invalid_credentials_error():
    """잘못된 인증 정보 에러"""
    return AuthenticationException("Invalid email or password")


def email_already_exists_error():
    """이메일 중복 에러 (단순화된 MVP 버전)"""
    return ConflictException("Email already registered")


def username_already_exists_error():
    """사용자명 중복 에러 (단순화된 MVP 버전)"""
    return ConflictException("Username already taken")


def invalid_token_error():
    """잘못된 토큰 에러"""
    return AuthenticationException("Invalid or expired token")


# CSRF 기능은 MVP에서 제거됨


# CSRF 기능은 MVP에서 제거됨


# inactive_user 기능은 MVP에서 제거됨


def password_validation_error():
    """비밀번호 검증 실패 에러"""
    return ValidationException(
        "Password validation failed",
        validation_errors=[
            ValidationError(
                field="password",
                message="Password must be 8-16 characters long and contain letters, numbers, and special characters"
            )
        ]
    )