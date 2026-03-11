"""
=============================================================================
JWT Token Utilities - JWT 토큰 디코드 및 검증
=============================================================================

📌 이 파일이 하는 일:
    JWT(JSON Web Token)을 디코드하고 검증합니다.
    토큰 생성은 user-service에서만 하고, 여기서는 검증만 합니다.

💡 JWT란?
    로그인 후 서버가 발급하는 "신분증" 같은 것입니다.

    구조: HEADER.PAYLOAD.SIGNATURE
    예시: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpM

    - HEADER: 알고리즘, 토큰 타입
    - PAYLOAD: 사용자 정보 (user_id, email 등)
    - SIGNATURE: 위조 방지 서명 (secret key로 생성)

🔄 검증 과정:
    1. 토큰을 "."으로 분리
    2. SIGNATURE를 secret key로 검증 (위조 여부)
    3. 만료 시간(exp) 확인
    4. 토큰 타입이 "access"인지 확인
    5. user_id(sub) 존재 확인

⚠️ 보안 주의사항:
    - jwt_secret_key는 절대 외부에 노출하면 안 됩니다
    - 운영 환경에서는 반드시 강력한 secret key 사용
"""

from typing import Optional
from dataclasses import dataclass
from jose import JWTError, jwt

from ..config import get_settings


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class JWTPayload:
    """
    📌 JWT 페이로드 데이터

    토큰에서 추출한 사용자 정보를 담는 클래스입니다.

    Attributes:
        user_id: 사용자 고유 ID (필수)
        email: 이메일 주소 (선택)
        username: 사용자명 (선택)
        exp: 만료 시간 (Unix timestamp, 선택)

    💡 @dataclass란?
        클래스를 만들 때 __init__, __repr__ 등을
        자동으로 생성해주는 편의 기능입니다.
    """
    user_id: str                     # JWT의 "sub" (subject) 필드에서 추출
    email: Optional[str] = None      # 이메일 (있으면 포함)
    username: Optional[str] = None   # 사용자명 (있으면 포함)
    exp: Optional[int] = None        # 만료 시간 (Unix timestamp)


# =============================================================================
# 토큰 검증 함수
# =============================================================================

def decode_access_token(token: str) -> Optional[JWTPayload]:
    """
    📌 JWT 액세스 토큰 디코드 및 검증

    토큰 문자열을 받아서 검증하고, 사용자 정보를 추출합니다.

    Args:
        token: JWT 토큰 문자열
               예: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

    Returns:
        JWTPayload: 검증 성공 시 사용자 정보
        None: 검증 실패 시 (만료, 위조, 형식 오류 등)

    검증 실패 케이스:
        - 토큰이 위조됨 (서명 불일치)
        - 토큰이 만료됨 (exp < 현재시간)
        - 토큰 타입이 "access"가 아님
        - user_id(sub)가 없음

    사용 예시:
        payload = decode_access_token(token)
        if payload:
            print(f"User ID: {payload.user_id}")
        else:
            print("Invalid token")
    """
    settings = get_settings()

    try:
        # =====================================================================
        # Step 1: 토큰 디코드 및 서명 검증
        # =====================================================================
        # jwt.decode()가 자동으로 다음을 확인합니다:
        # - 서명이 올바른지 (secret key로 검증)
        # - 토큰이 만료되지 않았는지 (exp 필드)
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,          # 서명 검증용 키
            algorithms=[settings.jwt_algorithm]  # 허용할 알고리즘 (HS256 등)
        )

        # =====================================================================
        # Step 2: 토큰 타입 확인
        # =====================================================================
        # 우리 시스템의 토큰은 "access"와 "refresh" 두 종류가 있습니다.
        # Gateway에서는 access 토큰만 허용합니다.
        if payload.get("type") != "access":
            return None

        # =====================================================================
        # Step 3: 필수 필드 확인
        # =====================================================================
        # "sub" (subject): JWT 표준에서 사용자 식별자를 담는 필드
        user_id = payload.get("sub")
        if not user_id:
            return None

        # =====================================================================
        # Step 4: 페이로드 객체 생성
        # =====================================================================
        return JWTPayload(
            user_id=user_id,
            email=payload.get("email"),      # 있으면 포함
            username=payload.get("username"),  # 있으면 포함
            exp=payload.get("exp")           # 만료 시간
        )

    except JWTError:
        # 모든 JWT 관련 에러 (만료, 서명 불일치, 형식 오류 등)
        # 보안상 구체적인 에러 내용은 로그에만 남기고
        # 클라이언트에게는 None만 반환
        return None
