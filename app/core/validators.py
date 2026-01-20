import re
from typing import Optional, List, Any, Union
from email_validator import validate_email, EmailNotValidError

from .errors import ValidationException, ValidationError


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
    def validate_string_length(
        value: str, 
        field_name: str, 
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> str:
        """문자열 길이 검증"""
        errors = []
        
        if min_length and len(value) < min_length:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"Must be at least {min_length} characters long",
                    value=len(value)
                )
            )
        
        if max_length and len(value) > max_length:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"Must be no more than {max_length} characters long",
                    value=len(value)
                )
            )
        
        if errors:
            raise ValidationException(
                f"{field_name} length validation failed",
                validation_errors=errors
            )
        
        return value
    
    @staticmethod
    def validate_email_format(email: str, field_name: str = "email") -> str:
        """이메일 형식 검증"""
        # 간단한 이메일 정규식 검증 (테스트용)
        import re
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
    def validate_enum(value: str, allowed_values: List[str], field_name: str) -> str:
        """열거형 값 검증"""
        if value not in allowed_values:
            raise ValidationException(
                f"Invalid {field_name}",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message=f"Must be one of: {', '.join(allowed_values)}",
                        value=value
                    )
                ]
            )
        return value
    
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

    @staticmethod
    def validate_message_content(content: str, field_name: str = "content") -> str:
        """메시지 내용 검증"""
        errors = []

        # 빈 메시지 검증
        if not content or content.strip() == "":
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Message content cannot be empty"
                )
            )

        # 최대 길이 검증 (5000자)
        if len(content) > 5000:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Message content must be no more than 5000 characters",
                    value=len(content)
                )
            )

        # 제어 문자 검증
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', content):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Message content contains invalid control characters"
                )
            )

        if errors:
            raise ValidationException(
                "Message content validation failed",
                validation_errors=errors
            )

        return content.strip()

    @staticmethod
    def validate_message_type(message_type: str, field_name: str = "message_type") -> str:
        """메시지 타입 검증"""
        allowed_types = ["text", "image", "file", "system"]
        return Validator.validate_enum(message_type, allowed_types, field_name)

    @staticmethod
    def validate_emoji(emoji: str, field_name: str = "emoji") -> str:
        """이모지 검증"""
        allowed_emojis = ['👍', '👎', '❤️', '😂', '😢', '😮', '😡', '🔥', '👏', '🎉']
        return Validator.validate_enum(emoji, allowed_emojis, field_name)

    @staticmethod
    def validate_search_query(query: str, field_name: str = "query") -> str:
        """검색 쿼리 검증"""
        errors = []

        # 최소 길이 검증
        if len(query.strip()) < 1:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Search query must be at least 1 character long"
                )
            )

        # 최대 길이 검증
        if len(query) > 100:
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Search query must be no more than 100 characters",
                    value=len(query)
                )
            )

        # 위험한 문자 검증 (SQL 인젝션 방지)
        dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
        for char in dangerous_chars:
            if char in query:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Search query contains dangerous character: {char}"
                    )
                )
                break

        if errors:
            raise ValidationException(
                "Search query validation failed",
                validation_errors=errors
            )

        return query.strip()

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str], field_name: str = "filename") -> str:
        """파일 확장자 검증"""
        if not filename:
            raise ValidationException(
                "Filename is required",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message="Filename cannot be empty"
                    )
                ]
            )

        file_ext = filename.lower().split('.')[-1] if '.' in filename else ""

        if not file_ext or f".{file_ext}" not in [ext.lower() for ext in allowed_extensions]:
            raise ValidationException(
                "Invalid file extension",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message=f"File extension must be one of: {', '.join(allowed_extensions)}",
                        value=f".{file_ext}" if file_ext else "none"
                    )
                ]
            )

        return filename

    @staticmethod
    def validate_file_size(file_size: int, max_size: int = 5 * 1024 * 1024, field_name: str = "file_size") -> int:
        """파일 크기 검증"""
        if file_size <= 0:
            raise ValidationException(
                "Invalid file size",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message="File size must be greater than 0",
                        value=file_size
                    )
                ]
            )

        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValidationException(
                "File size too large",
                validation_errors=[
                    ValidationError(
                        field=field_name,
                        message=f"File size must be no more than {max_size_mb:.1f}MB",
                        value=file_size
                    )
                ]
            )

        return file_size

    @staticmethod
    def validate_room_id(room_id: Union[int, str], field_name: str = "room_id") -> int:
        """채팅방 ID 검증"""
        return Validator.validate_positive_integer(room_id, field_name)

    @staticmethod
    def validate_pagination(limit: int, skip: int) -> tuple[int, int]:
        """페이지네이션 파라미터 검증"""
        errors = []

        # limit 검증
        if limit <= 0:
            errors.append(
                ValidationError(
                    field="limit",
                    message="Limit must be greater than 0",
                    value=limit
                )
            )
        elif limit > 100:
            errors.append(
                ValidationError(
                    field="limit",
                    message="Limit must be no more than 100",
                    value=limit
                )
            )

        # skip 검증
        if skip < 0:
            errors.append(
                ValidationError(
                    field="skip",
                    message="Skip must be 0 or greater",
                    value=skip
                )
            )

        if errors:
            raise ValidationException(
                "Pagination validation failed",
                validation_errors=errors
            )

        return limit, skip


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


def validate_user_update(
    email: Optional[str] = None,
    username: Optional[str] = None,
    display_name: Optional[str] = None
):
    """사용자 정보 수정 데이터 검증"""
    validator = Validator()
    validations = []
    
    if email is not None:
        validations.append(lambda: validator.validate_email_format(email))
    
    if username is not None:
        validations.append(lambda: validator.validate_username(username))
    
    if display_name is not None:
        validations.append(lambda: validator.validate_display_name(display_name))
    
    if validations:
        return validator.validate_multiple_fields(validations)

    return []


def validate_message_creation(content: str, message_type: str = "text", reply_to: Optional[str] = None):
    """메시지 생성 데이터 검증"""
    validator = Validator()

    validations = [
        lambda: validator.validate_message_content(content),
        lambda: validator.validate_message_type(message_type)
    ]

    return validator.validate_multiple_fields(validations)


def validate_message_search(query: str, limit: int = 20, skip: int = 0):
    """메시지 검색 데이터 검증"""
    validator = Validator()

    validations = [
        lambda: validator.validate_search_query(query),
        lambda: validator.validate_pagination(limit, skip)
    ]

    return validator.validate_multiple_fields(validations)


def validate_file_upload(filename: str, file_size: int, allowed_extensions: List[str] = None):
    """파일 업로드 데이터 검증"""
    if allowed_extensions is None:
        allowed_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

    validator = Validator()

    validations = [
        lambda: validator.validate_file_extension(filename, allowed_extensions),
        lambda: validator.validate_file_size(file_size)
    ]

    return validator.validate_multiple_fields(validations)