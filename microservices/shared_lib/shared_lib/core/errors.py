"""
=============================================================================
Error Handling (에러 처리) - 공통 예외 클래스
=============================================================================

📌 이 파일이 하는 일:
    MSA 서비스 전체에서 사용하는 공통 에러(예외) 클래스를 정의합니다.
    모든 서비스가 동일한 형식의 에러 응답을 반환하도록 합니다.

💡 왜 공통 에러가 필요한가요?
    1. 일관성: 모든 서비스가 같은 형식의 에러 응답 반환
    2. 코드 중복 제거: 각 서비스에서 에러 클래스를 따로 만들 필요 없음
    3. 클라이언트 편의: 프론트엔드가 에러를 쉽게 파싱할 수 있음

📊 에러 구조 (HTTP 상태 코드)
    BaseCustomException (기본 클래스)
    ├── ValidationException (422) - 입력 검증 실패
    │   예: 비밀번호가 너무 짧음, 이메일 형식 오류
    │
    ├── AuthenticationException (401) - 인증 실패
    │   예: 잘못된 비밀번호, 만료된 토큰
    │
    ├── AuthorizationException (403) - 권한 부족
    │   예: 관리자 전용 기능에 일반 사용자가 접근
    │
    ├── ResourceNotFoundException (404) - 리소스 없음
    │   예: 존재하지 않는 사용자 ID로 조회
    │
    ├── ConflictException (409) - 리소스 충돌
    │   예: 이미 존재하는 이메일로 회원가입
    │
    ├── BusinessLogicException (400) - 비즈니스 규칙 위반
    │   예: 자기 자신에게 친구 요청
    │
    ├── ExternalServiceException (502) - 외부 서비스 오류
    │   예: 결제 서비스 연결 실패
    │
    └── RateLimitException (429) - 요청 횟수 초과
        예: 1분에 100번 이상 요청

🔄 사용 예시:
    from shared_lib.core.errors import ResourceNotFoundException

    def get_user(user_id: int):
        user = db.find_user(user_id)
        if not user:
            raise ResourceNotFoundException("User")
        return user
"""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from pydantic import BaseModel


# =============================================================================
# 응답 모델 (Response Models)
# =============================================================================
# 클라이언트에게 반환할 에러 응답의 형식을 정의합니다

class ErrorResponse(BaseModel):
    """
    📌 표준 에러 응답 모델

    모든 에러는 이 형식으로 응답합니다.

    응답 예시:
        {
            "error": "resource_not_found",
            "message": "User not found",
            "details": {"user_id": 123},
            "status_code": 404
        }
    """
    error: str                               # 에러 코드 (프로그래밍용)
    message: str                             # 에러 메시지 (사용자용)
    details: Optional[Dict[str, Any]] = None # 추가 정보 (디버깅용)
    status_code: int                         # HTTP 상태 코드


class ValidationError(BaseModel):
    """
    📌 검증 에러 세부사항

    어떤 필드에서 어떤 검증이 실패했는지 알려줍니다.

    예시:
        {
            "field": "password",
            "message": "Password must be at least 8 characters",
            "value": 5  # 실제 입력된 길이
        }
    """
    field: str                    # 문제가 있는 필드 이름
    message: str                  # 에러 메시지
    value: Optional[Any] = None   # 실제 입력된 값 (디버깅용)


class ValidationErrorResponse(BaseModel):
    """
    📌 검증 에러 응답 모델

    여러 필드에서 동시에 검증이 실패했을 때 사용합니다.

    응답 예시:
        {
            "error": "validation_error",
            "message": "Multiple validation errors",
            "validation_errors": [
                {"field": "email", "message": "Invalid format"},
                {"field": "password", "message": "Too short"}
            ],
            "status_code": 422
        }
    """
    error: str = "validation_error"
    message: str
    validation_errors: List[ValidationError]  # 각 필드별 에러 목록
    status_code: int


# =============================================================================
# 예외 클래스 (Exception Classes)
# =============================================================================
# Python의 예외(Exception)는 에러 상황을 표현하는 특별한 객체입니다.
# raise 키워드로 발생시키고, try-except로 처리합니다.

class BaseCustomException(HTTPException):
    """
    📌 기본 커스텀 예외 클래스

    모든 커스텀 예외의 부모 클래스입니다.
    FastAPI의 HTTPException을 상속받아 HTTP 응답을 자동으로 생성합니다.

    💡 상속이란?
        부모 클래스의 기능을 물려받는 것입니다.
        BaseCustomException → HTTPException → Exception
    """
    def __init__(
        self,
        status_code: int,                        # HTTP 상태 코드 (200, 404 등)
        error: str,                              # 에러 코드
        message: str,                            # 에러 메시지
        details: Optional[Dict[str, Any]] = None # 추가 정보
    ):
        self.error = error
        self.message = message
        self.details = details
        self.status_code = status_code
        # 부모 클래스(HTTPException) 초기화
        super().__init__(status_code=status_code, detail=self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        """예외를 딕셔너리로 변환 (JSON 응답용)"""
        return {
            "error": self.error,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code
        }


class ValidationException(BaseCustomException):
    """
    📌 입력 검증 실패 예외 (HTTP 422)

    사용자 입력이 검증 규칙을 통과하지 못했을 때 발생합니다.

    사용 예시:
        if len(password) < 8:
            raise ValidationException(
                message="Password too short",
                validation_errors=[
                    ValidationError(field="password", message="At least 8 characters")
                ]
            )
    """
    def __init__(
        self,
        message: str = "Validation failed",
        validation_errors: Optional[List[ValidationError]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.validation_errors = validation_errors or []
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  # 422
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
    📌 인증 실패 예외 (HTTP 401)

    로그인에 실패하거나, 토큰이 유효하지 않을 때 발생합니다.

    사용 예시:
        if not verify_password(input_password, stored_hash):
            raise AuthenticationException("Invalid email or password")

        if token_expired:
            raise AuthenticationException("Token has expired")
    """
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,  # 401
            error="authentication_error",
            message=message,
            details=details
        )


class AuthorizationException(BaseCustomException):
    """
    📌 권한 부족 예외 (HTTP 403)

    인증은 되었지만, 해당 기능에 접근 권한이 없을 때 발생합니다.
    401(인증)과 403(권한)의 차이에 주의하세요!

    401: "당신이 누군지 모르겠어요" (로그인 안 됨)
    403: "당신이 누군지는 알지만, 이건 안 돼요" (권한 없음)

    사용 예시:
        if user.role != "admin":
            raise AuthorizationException("Admin access required")
    """
    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,  # 403
            error="authorization_error",
            message=message,
            details=details
        )


class ResourceNotFoundException(BaseCustomException):
    """
    📌 리소스를 찾을 수 없음 예외 (HTTP 404)

    요청한 리소스(사용자, 게시글, 채팅방 등)가 존재하지 않을 때 발생합니다.

    사용 예시:
        user = db.get_user(user_id)
        if not user:
            raise ResourceNotFoundException("User")

    결과: {"message": "User not found", "status_code": 404, ...}
    """
    def __init__(
        self,
        resource: str = "Resource",              # 리소스 종류 (User, ChatRoom 등)
        message: Optional[str] = None,           # 커스텀 메시지
        details: Optional[Dict[str, Any]] = None
    ):
        # 메시지가 없으면 기본 메시지 생성
        if message is None:
            message = f"{resource} not found"

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,  # 404
            error="resource_not_found",
            message=message,
            details=details or {"resource": resource}
        )


class ConflictException(BaseCustomException):
    """
    📌 리소스 충돌 예외 (HTTP 409)

    이미 존재하는 리소스와 충돌이 발생했을 때 사용합니다.

    사용 예시:
        existing_user = db.find_by_email(email)
        if existing_user:
            raise ConflictException("Email already registered")

        existing_friendship = db.find_friendship(user1, user2)
        if existing_friendship:
            raise ConflictException("Already friends")
    """
    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,  # 409
            error="resource_conflict",
            message=message,
            details=details
        )


class BusinessLogicException(BaseCustomException):
    """
    📌 비즈니스 로직 예외 (HTTP 400)

    입력은 유효하지만, 비즈니스 규칙에 위배될 때 사용합니다.

    사용 예시:
        # 기본 에러 코드 사용
        raise BusinessLogicException("Cannot send friend request to yourself")

        # 구체적인 에러 코드 사용 (Spring Boot ErrorCode와 대응)
        raise BusinessLogicException(
            "Cannot create chat room with yourself",
            error_code="CANNOT_CHAT_SELF"
        )

        # 상태 코드 커스텀 (422 등)
        raise BusinessLogicException(
            "Invalid input",
            error_code="INVALID_INPUT",
            status_code=422
        )
    """
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status_code,
            error=error_code or "business_logic_error",
            message=message,
            details=details
        )


class ExternalServiceException(BaseCustomException):
    """
    📌 외부 서비스 에러 예외 (HTTP 502)

    외부 서비스(결제, 이메일, 다른 마이크로서비스 등)와
    통신에 실패했을 때 사용합니다.

    사용 예시:
        try:
            response = payment_service.charge(amount)
        except ConnectionError:
            raise ExternalServiceException("PaymentService", "Connection failed")
    """
    def __init__(
        self,
        service: str,                            # 실패한 외부 서비스 이름
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,  # 502
            error="external_service_error",
            message=f"{service}: {message}",
            details=details or {"service": service}
        )


class RateLimitException(BaseCustomException):
    """
    📌 요청 제한 초과 예외 (HTTP 429)

    짧은 시간에 너무 많은 요청을 보냈을 때 발생합니다.
    DDoS 공격 방지와 서버 보호를 위해 사용합니다.

    사용 예시:
        if request_count > 100:
            raise RateLimitException(
                message="Too many requests",
                retry_after=60  # 60초 후 다시 시도
            )
    """
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,  # 재시도까지 대기 시간 (초)
        details: Optional[Dict[str, Any]] = None
    ):
        if retry_after:
            details = details or {}
            details["retry_after"] = retry_after

        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,  # 429
            error="rate_limit_exceeded",
            message=message,
            details=details
        )


# =============================================================================
# 헬퍼 함수 (Helper Functions)
# =============================================================================
# 에러 응답 객체를 쉽게 생성하기 위한 함수들입니다

def create_error_response(
    error: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None
) -> ErrorResponse:
    """
    📌 표준 에러 응답 생성

    에러 응답 객체를 간편하게 생성합니다.

    사용 예시:
        response = create_error_response(
            error="invalid_input",
            message="Name is required",
            status_code=400
        )
    """
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
    """
    📌 검증 에러 응답 생성

    여러 필드의 검증 에러를 하나의 응답으로 묶습니다.
    """
    return ValidationErrorResponse(
        message=message,
        validation_errors=validation_errors,
        status_code=status_code
    )


# =============================================================================
# 팩토리 함수 (Factory Functions)
# =============================================================================
# 자주 사용하는 에러를 쉽게 생성하기 위한 함수들입니다.
# 매번 에러 메시지를 작성하지 않아도 됩니다.
#
# 💡 팩토리 패턴이란?
#    객체 생성을 전담하는 함수/클래스를 만드는 패턴입니다.
#    복잡한 객체 생성 로직을 숨기고 간단하게 사용할 수 있습니다.

def user_not_found_error(user_id: Optional[int] = None):
    """
    📌 사용자를 찾을 수 없음 에러

    사용 예시:
        raise user_not_found_error(user_id=123)
        # → ResourceNotFoundException: "User not found"
    """
    details = {"user_id": user_id} if user_id else None
    return ResourceNotFoundException("User", details=details)


def invalid_credentials_error():
    """
    📌 잘못된 인증 정보 에러

    로그인 시 이메일 또는 비밀번호가 틀렸을 때 사용합니다.
    보안상 어느 쪽이 틀렸는지 알려주지 않습니다.

    사용 예시:
        raise invalid_credentials_error()
        # → AuthenticationException: "Invalid email or password"
    """
    return AuthenticationException("Invalid email or password")


def email_already_exists_error():
    """
    📌 이메일 중복 에러

    회원가입 시 이미 사용 중인 이메일로 가입 시도할 때 사용합니다.

    사용 예시:
        raise email_already_exists_error()
        # → ConflictException: "Email already registered"
    """
    return ConflictException("Email already registered")


def username_already_exists_error():
    """
    📌 사용자명 중복 에러

    회원가입 시 이미 사용 중인 사용자명으로 가입 시도할 때 사용합니다.

    사용 예시:
        raise username_already_exists_error()
        # → ConflictException: "Username already taken"
    """
    return ConflictException("Username already taken")


def invalid_token_error():
    """
    📌 잘못된 토큰 에러

    JWT 토큰이 유효하지 않거나 만료되었을 때 사용합니다.

    사용 예시:
        raise invalid_token_error()
        # → AuthenticationException: "Invalid or expired token"
    """
    return AuthenticationException("Invalid or expired token")


def password_validation_error():
    """
    📌 비밀번호 검증 실패 에러

    비밀번호가 보안 요구사항을 충족하지 않을 때 사용합니다.
    요구사항: 8-16자, 영문+숫자+특수문자 포함

    사용 예시:
        raise password_validation_error()
        # → ValidationException with password requirements
    """
    return ValidationException(
        "Password validation failed",
        validation_errors=[
            ValidationError(
                field="password",
                message="Password must be 8-16 characters long and contain letters, numbers, and special characters"
            )
        ]
    )
