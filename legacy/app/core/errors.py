"""
커스텀 예외 및 에러 핸들링 모듈 (Custom Exception & Error Handling Module)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
이 모듈은 애플리케이션 전체에서 사용되는 표준화된 에러 처리 시스템을 제공합니다.
계층화된 예외 클래스 구조를 통해 일관된 에러 응답 형식을 보장하며,
FastAPI의 HTTPException과 통합되어 자동으로 적절한 HTTP 상태 코드를 반환합니다.

에러 처리 흐름:
    비즈니스 로직 예외 발생 → Custom Exception 생성 → HTTPException 변환
                                                         ↓
    클라이언트 ← JSON 에러 응답 ← FastAPI 에러 핸들러 ←

================================================================================
예외 계층 구조 (Exception Hierarchy)
================================================================================
    HTTPException (FastAPI 기본)
           ↓
    BaseCustomException (기본 커스텀 예외)
           ↓
    ├── ValidationException (422 - 입력 검증 실패)
    ├── AuthenticationException (401 - 인증 실패)
    ├── AuthorizationException (403 - 권한 부족)
    ├── ResourceNotFoundException (404 - 리소스 없음)
    ├── ConflictException (409 - 리소스 충돌)
    ├── BusinessLogicException (400 - 비즈니스 로직 에러)
    ├── ExternalServiceException (502 - 외부 서비스 에러)
    └── RateLimitException (429 - 요청 제한 초과)

================================================================================
디자인 패턴 (Design Patterns)
================================================================================
1. Factory Pattern (팩토리 패턴)
   - 에러 팩토리 함수들 (user_not_found_error, invalid_credentials_error 등)
   - 자주 사용되는 에러를 간편하게 생성

2. Template Method Pattern (템플릿 메소드 패턴)
   - BaseCustomException의 to_dict() 메소드
   - 하위 클래스에서 오버라이드 가능

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================
- SRP (단일 책임): 각 예외 클래스는 하나의 에러 타입만 담당
- OCP (개방-폐쇄): 새로운 예외 타입 추가 시 기존 코드 수정 없이 확장 가능
- LSP (리스코프 치환): 모든 커스텀 예외는 BaseCustomException으로 대체 가능
- ISP (인터페이스 분리): 예외별로 필요한 속성만 정의

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.core.errors import ResourceNotFoundException, user_not_found_error
>>>
>>> # 직접 예외 생성
>>> raise ResourceNotFoundException("User", details={"user_id": 123})
>>>
>>> # 팩토리 함수 사용
>>> raise user_not_found_error(user_id=123)
>>>
>>> # ValidationException 사용
>>> from legacy.app.core.errors import ValidationException, ValidationError
>>> raise ValidationException(
...     message="입력 검증 실패",
...     validation_errors=[
...         ValidationError(field="email", message="유효하지 않은 이메일")
...     ]
... )
"""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """
    표준 에러 응답 모델

    모든 에러 응답의 기본 형식을 정의합니다.
    클라이언트는 이 형식에 맞춰 에러를 파싱할 수 있습니다.

    Attributes:
        error (str): 에러 타입 코드 (예: "authentication_error", "resource_not_found")
        message (str): 사용자 친화적인 에러 메시지
        details (Optional[Dict]): 추가 에러 정보 (선택사항)
        status_code (int): HTTP 상태 코드

    Example:
        {
            "error": "resource_not_found",
            "message": "User not found",
            "details": {"user_id": 123},
            "status_code": 404
        }
    """
    """표준 에러 응답 모델"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    status_code: int


class ValidationError(BaseModel):
    """
    검증 에러 세부사항

    개별 필드 검증 실패 시 해당 필드에 대한 상세 정보를 담습니다.

    Attributes:
        field (str): 검증 실패한 필드명
        message (str): 검증 실패 원인 설명
        value (Optional[Any]): 검증 실패한 실제 값 (디버깅용)

    Example:
        ValidationError(
            field="password",
            message="비밀번호는 8자 이상이어야 합니다",
            value=5  # 실제 입력된 비밀번호 길이
        )
    """
    field: str
    message: str
    value: Optional[Any] = None


class ValidationErrorResponse(BaseModel):
    """
    검증 에러 응답 모델

    여러 필드의 검증 에러를 한 번에 반환할 때 사용합니다.

    Attributes:
        error (str): 항상 "validation_error"
        message (str): 전체 검증 실패 요약 메시지
        validation_errors (List[ValidationError]): 개별 필드 에러 목록
        status_code (int): HTTP 상태 코드 (일반적으로 422)

    Example:
        ValidationErrorResponse(
            message="입력 데이터 검증 실패",
            validation_errors=[
                ValidationError(field="email", message="유효하지 않은 이메일"),
                ValidationError(field="password", message="비밀번호 형식 불일치")
            ],
            status_code=422
        )
    """
    error: str = "validation_error"
    message: str
    validation_errors: List[ValidationError]
    status_code: int


# =============================================================================
# 커스텀 예외 클래스들 (Custom Exception Classes)
# =============================================================================
# 모든 비즈니스 로직 예외의 기본이 되는 클래스들입니다.
# FastAPI의 HTTPException을 상속하여 자동으로 HTTP 응답으로 변환됩니다.
# =============================================================================

class BaseCustomException(HTTPException):
    """
    기본 커스텀 예외 클래스

    모든 애플리케이션 예외의 부모 클래스입니다.
    FastAPI HTTPException을 상속하여 자동으로 적절한 HTTP 응답을 생성합니다.

    Attributes:
        error (str): 에러 타입 식별자
        message (str): 사용자 친화적 에러 메시지
        details (Optional[Dict]): 추가 컨텍스트 정보
        status_code (int): HTTP 상태 코드

    Example:
        >>> raise BaseCustomException(
        ...     status_code=400,
        ...     error="custom_error",
        ...     message="Something went wrong",
        ...     details={"reason": "invalid input"}
        ... )
    """
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
    """
    입력 검증 실패 예외 (HTTP 422 Unprocessable Entity)

    사용자 입력이 유효성 검사를 통과하지 못했을 때 발생합니다.
    여러 필드의 에러를 한 번에 담아서 반환할 수 있습니다.

    Example:
        >>> raise ValidationException(
        ...     message="회원가입 데이터 검증 실패",
        ...     validation_errors=[
        ...         ValidationError(field="email", message="이메일 형식이 올바르지 않습니다"),
        ...         ValidationError(field="password", message="비밀번호는 8자 이상이어야 합니다")
        ...     ]
        ... )
    """
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
    """
    인증 실패 예외 (HTTP 401 Unauthorized)

    사용자 인증이 필요하거나 인증에 실패했을 때 발생합니다.
    - 토큰이 없거나 만료됨
    - 잘못된 이메일/비밀번호
    - 유효하지 않은 토큰 형식

    Example:
        >>> raise AuthenticationException(message="토큰이 만료되었습니다")
    """
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
    """
    권한 부족 예외 (HTTP 403 Forbidden)

    인증된 사용자가 해당 리소스에 대한 권한이 없을 때 발생합니다.
    - 다른 사용자의 메시지 삭제 시도
    - 참여하지 않은 채팅방 접근
    - 관리자 전용 기능 접근

    Example:
        >>> raise AuthorizationException(
        ...     message="이 채팅방에 접근할 권한이 없습니다",
        ...     details={"room_id": 123}
        ... )
    """
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
    """
    리소스를 찾을 수 없음 예외 (HTTP 404 Not Found)

    요청한 리소스가 존재하지 않을 때 발생합니다.
    - 존재하지 않는 사용자 ID
    - 삭제된 채팅방
    - 없는 메시지 ID

    Example:
        >>> raise ResourceNotFoundException("User", details={"user_id": 999})
        # 결과: {"error": "resource_not_found", "message": "User not found", ...}
    """
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
    """
    리소스 충돌 예외 (HTTP 409 Conflict)

    리소스 생성/수정 시 기존 리소스와 충돌이 발생했을 때 발생합니다.
    - 이미 등록된 이메일로 회원가입
    - 중복된 사용자명
    - 이미 친구인 사용자에게 친구 요청

    Example:
        >>> raise ConflictException(message="이미 등록된 이메일입니다")
    """
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
    """
    비즈니스 로직 예외 (HTTP 400 Bad Request)

    비즈니스 규칙 위반 시 발생하는 일반적인 예외입니다.
    다른 구체적인 예외 타입에 해당하지 않는 경우 사용합니다.
    - 자기 자신과의 채팅방 생성 시도
    - 빈 메시지 전송
    - 삭제된 메시지 수정 시도

    Example:
        >>> raise BusinessLogicException(message="자기 자신에게 친구 요청을 보낼 수 없습니다")
    """
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
    """
    외부 서비스 에러 예외 (HTTP 502 Bad Gateway)

    외부 서비스(Redis, Kafka, 외부 API 등) 호출 실패 시 발생합니다.
    - Redis 연결 실패
    - Kafka 메시지 발행 실패
    - 외부 API 타임아웃

    Example:
        >>> raise ExternalServiceException(
        ...     service="Redis",
        ...     message="연결 시간 초과"
        ... )
    """
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
    """
    요청 제한 초과 예외 (HTTP 429 Too Many Requests)

    Rate Limiting 규칙에 의해 요청이 거부되었을 때 발생합니다.
    retry_after 필드를 통해 재시도까지 대기 시간을 알려줍니다.

    Example:
        >>> raise RateLimitException(
        ...     message="너무 많은 요청입니다",
        ...     retry_after=30  # 30초 후 재시도
        ... )
    """
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
# 에러 헬퍼 함수들 (Error Helper Functions)
# =============================================================================
# 표준 에러 응답 모델을 생성하는 유틸리티 함수들입니다.
# API 응답에서 일관된 에러 형식을 보장합니다.
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
# 에러 팩토리 함수들 (Error Factory Functions)
# =============================================================================
# 자주 발생하는 에러를 간편하게 생성하는 팩토리 함수들입니다.
# 코드 중복을 줄이고 일관된 에러 메시지를 보장합니다.
#
# 사용 예시:
#     from legacy.app.core.errors import user_not_found_error
#     raise user_not_found_error(user_id=123)
# =============================================================================

def user_not_found_error(user_id: Optional[int] = None):
    """
    사용자를 찾을 수 없음 에러 생성

    Args:
        user_id: 찾지 못한 사용자 ID (선택사항)

    Returns:
        ResourceNotFoundException: 사용자 미발견 예외

    Example:
        >>> raise user_not_found_error(user_id=123)
    """
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