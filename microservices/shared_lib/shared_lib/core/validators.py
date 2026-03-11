"""
=============================================================================
Validators (검증 유틸리티) - 입력 데이터 검증
=============================================================================

📌 이 파일이 하는 일:
    사용자 입력 데이터가 올바른 형식인지 검증합니다.
    모든 서비스에서 동일한 검증 규칙을 사용하도록 공통화했습니다.

💡 왜 검증이 필요한가요?
    1. 보안: SQL Injection, XSS 등 공격 방지
    2. 데이터 품질: 잘못된 데이터가 DB에 저장되는 것 방지
    3. 사용자 경험: 명확한 에러 메시지 제공

📊 검증 규칙:
    - 이메일: xxx@xxx.xxx 형식 (RFC 5322)
    - 비밀번호: 8-16자, 영문+숫자+특수문자 모두 포함
    - 사용자명: 3-50자, 영문+숫자+언더스코어+하이픈만 허용

🔄 사용 예시:
    from shared_lib.core.validators import Validator

    validator = Validator()

    # 개별 검증
    validator.validate_email_format("user@example.com")  # OK
    validator.validate_email_format("invalid-email")     # ValidationException

    # 전체 회원가입 검증
    validate_user_registration(
        email="user@example.com",
        username="john_doe",
        password="SecurePass1!"
    )
"""

import re
from typing import Optional, List, Any, Union

from .errors import ValidationException, ValidationError


# =============================================================================
# 검증 클래스
# =============================================================================

class Validator:
    """
    📌 입력 검증을 위한 유틸리티 클래스

    모든 검증 메서드는 @staticmethod로 선언되어 있어서
    인스턴스 생성 없이도 사용할 수 있습니다.

    사용 예시:
        # 인스턴스 없이 직접 호출
        Validator.validate_email_format("test@example.com")

        # 인스턴스로도 사용 가능
        validator = Validator()
        validator.validate_email_format("test@example.com")
    """

    @staticmethod
    def validate_required(value: Any, field_name: str) -> Any:
        """
        📌 필수 필드 검증

        값이 None이거나 빈 문자열이면 에러를 발생시킵니다.

        Args:
            value: 검증할 값
            field_name: 필드 이름 (에러 메시지에 표시)

        Returns:
            입력값 그대로 (검증 통과 시)

        Raises:
            ValidationException: 값이 없거나 빈 문자열인 경우

        예시:
            validate_required("hello", "username")  # OK, "hello" 반환
            validate_required("", "username")       # ValidationException 발생
            validate_required(None, "username")     # ValidationException 발생
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise ValidationException(
                f"{field_name} is required",
                validation_errors=[
                    ValidationError(field=field_name, message="This field is required", value=value)
                ]
            )
        return value

    @staticmethod
    def validate_email_format(email: str, field_name: str = "email") -> str:
        """
        📌 이메일 형식 검증

        이메일이 올바른 형식(xxx@xxx.xxx)인지 확인합니다.

        Args:
            email: 검증할 이메일 주소
            field_name: 필드 이름 (기본값: "email")

        Returns:
            입력 이메일 그대로 (검증 통과 시)

        Raises:
            ValidationException: 이메일 형식이 올바르지 않은 경우

        유효한 예시:
            user@example.com ✅
            user.name+tag@example.co.kr ✅

        무효한 예시:
            user@example ❌ (도메인 불완전)
            @example.com ❌ (사용자명 없음)
            user.example.com ❌ (@ 없음)
        """
        # 이메일 정규식 패턴
        # ^ : 시작
        # [a-zA-Z0-9._%+-]+ : 사용자명 (영문, 숫자, 특수문자)
        # @ : 골뱅이
        # [a-zA-Z0-9.-]+ : 도메인명
        # \.[a-zA-Z]{2,}$ : .com, .co.kr 등 (최소 2글자)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_pattern, email):
            raise ValidationException(
                "Invalid email format",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message="Invalid email format",
                        value=email
                    )
                ]
            )
        return email

    @staticmethod
    def validate_password_strength(password: str, field_name: str = "password") -> str:
        """
        📌 비밀번호 강도 검증

        비밀번호가 보안 요구사항을 충족하는지 확인합니다.

        요구사항:
            - 길이: 8~16자
            - 영문자 최소 1개 (a-z, A-Z)
            - 숫자 최소 1개 (0-9)
            - 특수문자 최소 1개 (!@#$%^&* 등)

        Args:
            password: 검증할 비밀번호
            field_name: 필드 이름 (기본값: "password")

        Returns:
            입력 비밀번호 그대로 (검증 통과 시)

        Raises:
            ValidationException: 요구사항을 충족하지 않는 경우

        유효한 예시:
            Abcd1234! ✅ (영문+숫자+특수문자, 9자)
            P@ssw0rd ✅ (영문+숫자+특수문자, 8자)

        무효한 예시:
            password ❌ (숫자, 특수문자 없음)
            12345678 ❌ (영문, 특수문자 없음)
            Abc123 ❌ (7자, 특수문자 없음)
        """
        errors = []

        # 길이 검증 (8-16자)
        if len(password) < 8:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must be at least 8 characters long",
                    value=len(password)
                )
            )
        elif len(password) > 16:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must be no more than 16 characters long",
                    value=len(password)
                )
            )

        # 영문자 포함 검증
        if not re.search(r'[a-zA-Z]', password):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must contain at least one letter"
                )
            )

        # 숫자 포함 검증
        if not re.search(r'\d', password):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must contain at least one digit"
                )
            )

        # 특수문자 포함 검증
        special_chars = r'!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~'
        if not re.search(f'[{re.escape(special_chars)}]', password):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must contain at least one special character"
                )
            )

        # 에러가 있으면 예외 발생
        if errors:
            raise ValidationException(
                "Password does not meet security requirements",
                validation_errors=errors
            )

        return password

    @staticmethod
    def validate_username(username: str, field_name: str = "username") -> str:
        """
        📌 사용자명 검증

        사용자명이 규칙에 맞는지 확인합니다.

        요구사항:
            - 길이: 3~50자
            - 허용 문자: 영문, 숫자, 언더스코어(_), 하이픈(-)
            - 첫 글자: 영문 또는 숫자 (특수문자로 시작 불가)

        Args:
            username: 검증할 사용자명
            field_name: 필드 이름 (기본값: "username")

        Returns:
            입력 사용자명 그대로 (검증 통과 시)

        Raises:
            ValidationException: 규칙을 충족하지 않는 경우

        유효한 예시:
            john_doe ✅
            user123 ✅
            my-name ✅

        무효한 예시:
            ab ❌ (2자, 최소 3자 필요)
            _username ❌ (특수문자로 시작)
            user@name ❌ (허용되지 않는 문자 @)
        """
        errors = []

        # 길이 검증 (3-50자)
        if len(username) < 3:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Username must be at least 3 characters long",
                    value=len(username)
                )
            )
        elif len(username) > 50:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Username must be no more than 50 characters long",
                    value=len(username)
                )
            )

        # 허용 문자 검증 (영문, 숫자, _, -)
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Username can only contain letters, numbers, underscores, and hyphens"
                )
            )

        # 첫 글자 검증 (영문 또는 숫자)
        if not re.match(r'^[a-zA-Z0-9]', username):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Username must start with a letter or number"
                )
            )

        if errors:
            raise ValidationException(
                "Username validation failed",
                validation_errors=errors
            )

        return username

    @staticmethod
    def validate_display_name(display_name: Optional[str], field_name: str = "display_name") -> Optional[str]:
        """
        📌 표시명(닉네임) 검증

        표시명이 규칙에 맞는지 확인합니다.
        표시명은 선택 사항이므로 None이나 빈 문자열도 허용합니다.

        요구사항:
            - 최대 100자
            - 제어 문자(탭, 개행 등) 포함 불가

        Args:
            display_name: 검증할 표시명 (None 가능)
            field_name: 필드 이름 (기본값: "display_name")

        Returns:
            정리된 표시명 또는 None

        Raises:
            ValidationException: 규칙을 충족하지 않는 경우
        """
        # None이나 빈 문자열이면 None 반환
        if display_name is None or display_name.strip() == "":
            return None

        # 앞뒤 공백 제거
        display_name = display_name.strip()

        # 길이 검증 (최대 100자)
        if len(display_name) > 100:
            raise ValidationException(
                "Display name is too long",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message="Display name must be no more than 100 characters long",
                        value=len(display_name)
                    )
                ]
            )

        # 제어 문자 검증 (탭, 개행, 특수 제어 문자 등)
        # \x00-\x1f: ASCII 제어 문자 (0-31)
        # \x7f: DEL 문자
        if re.search(r'[\x00-\x1f\x7f]', display_name):
            raise ValidationException(
                "Display name contains invalid characters",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message="Display name cannot contain control characters"
                    )
                ]
            )

        return display_name

    @staticmethod
    def validate_positive_integer(value: Union[int, str], field_name: str) -> int:
        """
        📌 양의 정수 검증

        값이 1 이상의 정수인지 확인합니다.
        문자열로 전달된 숫자도 변환해서 검증합니다.

        Args:
            value: 검증할 값 (int 또는 str)
            field_name: 필드 이름 (에러 메시지에 표시)

        Returns:
            int: 변환된 정수값

        Raises:
            ValidationException: 양의 정수가 아닌 경우

        예시:
            validate_positive_integer(5, "user_id")   # OK, 5 반환
            validate_positive_integer("10", "count")  # OK, 10 반환
            validate_positive_integer(0, "page")      # ValidationException
            validate_positive_integer(-1, "id")       # ValidationException
        """
        try:
            int_value = int(value)
            if int_value <= 0:
                raise ValueError("Must be positive")
            return int_value
        except (ValueError, TypeError):
            raise ValidationException(
                f"{field_name} must be a positive integer",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message="Must be a positive integer",
                        value=value
                    )
                ]
            )

    @staticmethod
    def validate_multiple_fields(validations: List[callable]) -> List[Any]:
        """
        📌 여러 필드 동시 검증

        여러 검증 함수를 한 번에 실행하고,
        모든 에러를 수집해서 한 번에 반환합니다.

        하나의 필드만 검증 실패해도 바로 에러를 반환하면
        사용자가 여러 번 수정해야 합니다.
        이 함수를 사용하면 모든 에러를 한 번에 알려줄 수 있습니다.

        Args:
            validations: 검증 함수 리스트 (lambda 권장)

        Returns:
            List[Any]: 각 검증 함수의 반환값 리스트

        Raises:
            ValidationException: 하나 이상의 검증이 실패한 경우

        예시:
            validator = Validator()
            results = validator.validate_multiple_fields([
                lambda: validator.validate_email_format("bad-email"),
                lambda: validator.validate_password_strength("123"),
            ])
            # → 이메일과 비밀번호 에러를 모두 포함한 ValidationException 발생
        """
        errors = []   # 모든 에러 수집
        results = []  # 검증 통과한 결과 수집

        for validation_func in validations:
            try:
                result = validation_func()
                results.append(result)
            except ValidationException as e:
                # 에러 발생해도 멈추지 않고 모든 에러 수집
                errors.extend(e.validation_errors)

        # 에러가 있으면 모든 에러를 포함한 예외 발생
        if errors:
            raise ValidationException(
                "Multiple validation errors",
                validation_errors=errors
            )

        return results


# =============================================================================
# 편의 함수 (Convenience Functions)
# =============================================================================
# 자주 사용하는 검증 조합을 미리 정의해둔 함수들입니다.
# 서비스에서 바로 가져다 사용할 수 있습니다.

def validate_user_registration(email: str, username: str, password: str, display_name: Optional[str] = None):
    """
    📌 회원가입 데이터 전체 검증

    회원가입 시 필요한 모든 필드를 한 번에 검증합니다.
    하나의 필드라도 실패하면 모든 에러를 수집해서 반환합니다.

    Args:
        email: 이메일 주소
        username: 사용자명
        password: 비밀번호
        display_name: 표시명 (선택)

    Raises:
        ValidationException: 하나 이상의 검증이 실패한 경우

    사용 예시:
        from shared_lib.core.validators import validate_user_registration

        # 서비스 레이어에서 사용
        def register_user(request: RegisterRequest):
            validate_user_registration(
                email=request.email,
                username=request.username,
                password=request.password,
                display_name=request.display_name
            )
            # 검증 통과하면 여기 도달
            # 실패하면 ValidationException이 발생하고 여기에 도달 안 함
    """
    validator = Validator()

    # 검증할 함수 목록 (lambda로 감싸서 지연 실행)
    validations = [
        lambda: validator.validate_required(email, "email"),       # 이메일 필수
        lambda: validator.validate_email_format(email),            # 이메일 형식
        lambda: validator.validate_required(username, "username"), # 사용자명 필수
        lambda: validator.validate_username(username),             # 사용자명 규칙
        lambda: validator.validate_required(password, "password"), # 비밀번호 필수
        lambda: validator.validate_password_strength(password),    # 비밀번호 강도
        lambda: validator.validate_display_name(display_name) if display_name else display_name
    ]

    return validator.validate_multiple_fields(validations)


def validate_user_login(email: str, password: str):
    """
    📌 로그인 데이터 검증

    로그인 시 입력된 이메일과 비밀번호 형식을 검증합니다.

    ⚠️ 주의: 이 함수는 형식만 검증합니다.
       실제 비밀번호가 맞는지는 서비스 레이어에서 확인해야 합니다.

    Args:
        email: 이메일 주소
        password: 비밀번호

    Raises:
        ValidationException: 검증 실패 시

    사용 예시:
        def login(request: LoginRequest):
            # 1. 형식 검증
            validate_user_login(request.email, request.password)

            # 2. 사용자 조회
            user = db.find_by_email(request.email)

            # 3. 비밀번호 확인 (별도 로직)
            if not verify_password(request.password, user.password_hash):
                raise invalid_credentials_error()
    """
    validator = Validator()

    validations = [
        lambda: validator.validate_required(email, "email"),
        lambda: validator.validate_email_format(email),
        lambda: validator.validate_required(password, "password")
        # 로그인에서는 비밀번호 강도 검증 안 함
        # (이미 가입할 때 검증했으므로)
    ]

    return validator.validate_multiple_fields(validations)
