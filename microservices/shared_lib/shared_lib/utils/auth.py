"""
=============================================================================
JWT Token Utilities (JWT 토큰 유틸리티) - 공통 인증 유틸
=============================================================================

📌 이 파일이 하는 일:
    JWT(JSON Web Token) 토큰을 검증(디코드)하는 공통 유틸리티입니다.
    friend-service, chat-service 등에서 사용자 인증 시 사용합니다.

⚠️ 중요:
    - 이 파일은 토큰 "검증"만 담당합니다
    - 토큰 "생성"과 "비밀번호 해싱"은 user-service에서만 처리합니다
    - 모든 서비스가 같은 secret_key를 사용해야 토큰 검증이 가능합니다

💡 JWT란?
    로그인 후 서버가 발급하는 "신분증" 같은 것입니다.

    JWT 구조: HEADER.PAYLOAD.SIGNATURE
    예시: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpM

    - HEADER: 알고리즘 정보 (HS256 등)
    - PAYLOAD: 사용자 정보 (user_id, email, 만료시간 등)
    - SIGNATURE: 위조 방지 서명 (secret_key로 생성)

🔄 사용 흐름:
    1. 클라이언트가 Authorization: Bearer {token} 헤더로 요청
    2. 서비스에서 decode_access_token()으로 토큰 검증
    3. 유효하면 페이로드에서 user_id 추출
    4. 유효하지 않으면 401 Unauthorized 응답

사용 예시
---------
```python
from shared_lib.utils import decode_access_token

# 토큰 검증
payload = decode_access_token(token, secret_key, algorithm)
if payload:
    user_id = payload.get("sub")  # 사용자 ID
    email = payload.get("email")   # 이메일
else:
    # 토큰이 유효하지 않음 (만료, 위조, 형식 오류 등)
    raise AuthenticationException("Invalid token")
```

관련 파일
---------
- user-service/app/utils/auth.py: 토큰 생성, 비밀번호 해싱 (완전한 버전)
- api-gateway/app/auth/jwt.py: Gateway용 토큰 검증
"""

from typing import Optional, Dict, Any
from jose import JWTError, jwt


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256"
) -> Optional[Dict[str, Any]]:
    """
    📌 JWT 액세스 토큰 디코드 및 검증

    토큰의 서명을 검증하고, 페이로드(사용자 정보)를 추출합니다.

    Args:
        token: JWT 토큰 문자열
               예: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        secret_key: JWT 서명 검증용 시크릿 키
                    user-service와 동일한 키를 사용해야 함
        algorithm: JWT 알고리즘 (기본값: HS256)
                   HMAC-SHA256을 사용한 대칭키 서명

    Returns:
        dict: 검증 성공 시 페이로드
              예: {"sub": "123", "email": "user@example.com", "exp": 1234567890}
        None: 검증 실패 시 (만료, 서명 불일치, 형식 오류 등)

    검증 항목:
        1. 서명 유효성 (secret_key로 검증)
        2. 만료 시간 (exp 클레임)
        3. 토큰 타입 (type == "access")

    페이로드 클레임 설명:
        - sub: 사용자 ID (Subject)
        - email: 사용자 이메일
        - username: 사용자명
        - exp: 만료 시간 (Unix timestamp)
        - type: 토큰 타입 ("access" 또는 "refresh")

    사용 예시:
        # 기본 사용
        payload = decode_access_token(token, "my-secret-key")

        # 검증 결과 확인
        if payload:
            user_id = payload.get("sub")
            print(f"User ID: {user_id}")
        else:
            print("Invalid or expired token")

    보안 참고:
        - algorithms 파라미터로 허용 알고리즘을 명시적으로 지정
        - 알고리즘 혼동 공격(Algorithm Confusion Attack) 방지
    """
    try:
        # JWT 디코드 및 서명 검증
        # jwt.decode()가 자동으로 확인하는 것들:
        # - 서명이 올바른지 (secret_key로 검증)
        # - 토큰이 만료되지 않았는지 (exp 클레임)
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm]  # 허용할 알고리즘 명시 (보안)
        )

        # 토큰 타입 확인
        # 우리 시스템은 "access"와 "refresh" 두 종류의 토큰을 사용합니다
        # 여기서는 access 토큰만 허용합니다
        if payload.get("type") != "access":
            return None

        return payload

    except JWTError:
        # 모든 JWT 관련 에러를 캐치
        # - ExpiredSignatureError: 토큰 만료
        # - InvalidSignatureError: 서명 불일치 (위조 시도)
        # - DecodeError: 형식 오류
        # 보안상 구체적인 에러 내용은 노출하지 않고 None 반환
        return None
