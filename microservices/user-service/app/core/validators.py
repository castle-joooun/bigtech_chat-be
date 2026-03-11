"""
Input Validation Module (입력 검증 모듈)
=======================================

이 모듈은 shared_lib.core.validators를 re-export합니다.
기존 코드와의 호환성을 위해 유지됩니다.

사용 예시:
    from app.core.validators import Validator, validate_user_registration
    # 또는
    from shared_lib.core import Validator, validate_user_registration
"""

# shared_lib에서 모든 검증 클래스/함수 re-export
from shared_lib.core.validators import (
    Validator,
    validate_user_registration,
    validate_user_login,
)

__all__ = [
    "Validator",
    "validate_user_registration",
    "validate_user_login",
]
