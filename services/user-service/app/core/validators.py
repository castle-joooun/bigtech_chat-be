import re
from typing import Optional, List, Any, Union

from app.core.errors import ValidationException, ValidationError


class Validator:
    """입력 검증을 위한 유틸리티 클래스"""

    @staticmethod
    def validate_required(value: Any, field_name: str) -> Any:
        """필수 필드 검증"""
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
        """이메일 형식 검증"""
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
        """비밀번호 강도 검증"""
        errors = []

        # 길이 검사 (8-16자)
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

        # 영문자 포함 검사
        if not re.search(r'[a-zA-Z]', password):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must contain at least one letter"
                )
            )

        # 숫자 포함 검사
        if not re.search(r'\d', password):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must contain at least one digit"
                )
            )

        # 특수문자 포함 검사
        special_chars = r'!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~'
        if not re.search(f'[{re.escape(special_chars)}]', password):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Password must contain at least one special character"
                )
            )

        if errors:
            raise ValidationException(
                "Password does not meet security requirements",
                validation_errors=errors
            )

        return password

    @staticmethod
    def validate_username(username: str, field_name: str = "username") -> str:
        """사용자명 검증"""
        errors = []

        # 길이 검증
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

        # 허용된 문자 검증 (영문자, 숫자, 언더스코어, 하이픈)
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Username can only contain letters, numbers, underscores, and hyphens"
                )
            )

        # 시작 문자 검증 (영문자나 숫자로 시작)
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
        """표시명 검증"""
        if display_name is None or display_name.strip() == "":
            return None

        display_name = display_name.strip()

        # 길이 검증
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

        # 금지된 문자 검증 (제어 문자 제외)
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
        """양의 정수 검증"""
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
        """여러 필드 동시 검증"""
        errors = []
        results = []

        for validation_func in validations:
            try:
                result = validation_func()
                results.append(result)
            except ValidationException as e:
                errors.extend(e.validation_errors)

        if errors:
            raise ValidationException(
                "Multiple validation errors",
                validation_errors=errors
            )

        return results


# 편의 함수들
def validate_user_registration(email: str, username: str, password: str, display_name: Optional[str] = None):
    """사용자 등록 데이터 전체 검증"""
    validator = Validator()

    validations = [
        lambda: validator.validate_required(email, "email"),
        lambda: validator.validate_email_format(email),
        lambda: validator.validate_required(username, "username"),
        lambda: validator.validate_username(username),
        lambda: validator.validate_required(password, "password"),
        lambda: validator.validate_password_strength(password),
        lambda: validator.validate_display_name(display_name) if display_name else display_name
    ]

    return validator.validate_multiple_fields(validations)


def validate_user_login(email: str, password: str):
    """사용자 로그인 데이터 검증"""
    validator = Validator()

    validations = [
        lambda: validator.validate_required(email, "email"),
        lambda: validator.validate_email_format(email),
        lambda: validator.validate_required(password, "password")
    ]

    return validator.validate_multiple_fields(validations)
