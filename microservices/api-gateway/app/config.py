"""
=============================================================================
API Gateway Configuration - 환경 설정 관리
=============================================================================

📌 이 파일이 하는 일:
    API Gateway의 모든 설정을 한 곳에서 관리합니다.
    환경 변수나 .env 파일에서 값을 읽어옵니다.

💡 환경 변수란?
    운영체제에서 프로그램에게 전달하는 설정값입니다.
    같은 코드를 개발/운영 환경에서 다르게 동작시킬 수 있습니다.

    예시:
        개발 환경: DEBUG=true, user_service_url=http://localhost:8005
        운영 환경: DEBUG=false, user_service_url=http://user-service:8005

🔧 설정 우선순위:
    1. 환경 변수 (최우선)
    2. .env 파일
    3. 코드의 기본값 (default)

📝 설정 변경 방법:
    방법 1) 환경 변수 설정
        export DEBUG=true
        export USER_SERVICE_URL=http://localhost:8005

    방법 2) .env 파일 생성
        DEBUG=true
        USER_SERVICE_URL=http://localhost:8005
"""

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """
    📌 Gateway 설정 클래스

    Pydantic Settings를 사용해서 환경 변수를 자동으로 읽어옵니다.
    변수명이 대소문자 구분 없이 매칭됩니다.

    예: user_service_url ← USER_SERVICE_URL 환경 변수
    """

    # =========================================================================
    # 애플리케이션 기본 설정
    # =========================================================================
    app_name: str = "API Gateway"  # API 문서에 표시될 이름
    debug: bool = False            # True면 디버그 모드 (API 문서 활성화 등)

    # =========================================================================
    # 서버 설정
    # =========================================================================
    host: str = "0.0.0.0"  # 접속 허용 IP (0.0.0.0 = 모든 IP에서 접속 가능)
    port: int = 8000       # 서버 포트 번호

    # =========================================================================
    # 백엔드 서비스 URL
    # =========================================================================
    # Docker/K8s 환경에서는 서비스 이름으로 접근 (DNS 자동 해석)
    # 로컬 개발 시에는 localhost로 변경 필요
    user_service_url: str = "http://user-service:8005"    # 사용자 서비스
    friend_service_url: str = "http://friend-service:8003"  # 친구 서비스
    chat_service_url: str = "http://chat-service:8002"    # 채팅 서비스

    # =========================================================================
    # 타임아웃 설정
    # =========================================================================
    # 백엔드 서비스 응답 대기 시간 (초)
    # 이 시간이 지나면 타임아웃 에러 반환
    default_timeout: float = 30.0

    # =========================================================================
    # CORS 설정 (Cross-Origin Resource Sharing)
    # =========================================================================
    # CORS: 다른 도메인에서 API 호출을 허용하는 설정
    # 예: http://localhost:3000 (프론트) → http://localhost:8000 (API)

    cors_origins: List[str] = ["*"]      # 허용할 도메인 (* = 모두 허용, 개발용)
                                          # 운영: ["https://bigtech-chat.com"]
    cors_allow_credentials: bool = True   # 쿠키 전송 허용
    cors_allow_methods: List[str] = ["*"] # 허용할 HTTP 메서드 (GET, POST 등)
    cors_allow_headers: List[str] = ["*"] # 허용할 요청 헤더

    # =========================================================================
    # Rate Limiting 설정 (요청 횟수 제한)
    # =========================================================================
    # DDoS 공격이나 과도한 요청을 막기 위해 사용
    rate_limit_per_minute: int = 100  # 분당 최대 요청 수
    rate_limit_enabled: bool = True   # Rate Limiting 활성화 여부

    # =========================================================================
    # 보안 설정
    # =========================================================================
    xss_protection_enabled: bool = True           # XSS 공격 방지
    sql_injection_protection_enabled: bool = True  # SQL Injection 방지

    # =========================================================================
    # JWT 인증 설정
    # =========================================================================
    # JWT: JSON Web Token (로그인 후 발급받는 인증 토큰)
    jwt_secret_key: str = "your-secret-key-change-in-production"  # 토큰 서명 키
                          # ⚠️ 운영 환경에서는 반드시 변경 필요!
    jwt_algorithm: str = "HS256"  # 토큰 암호화 알고리즘

    class Config:
        """Pydantic Settings 설정"""
        env_file = ".env"          # .env 파일에서 설정 읽기
        env_file_encoding = "utf-8"
        extra = "ignore"           # 알 수 없는 환경 변수는 무시


# =============================================================================
# 설정 인스턴스 캐싱
# =============================================================================

@lru_cache()
def get_settings() -> Settings:
    """
    📌 캐시된 설정 인스턴스 반환

    @lru_cache() 데코레이터가 결과를 캐싱합니다.
    처음 호출할 때 Settings 객체를 만들고,
    이후 호출에서는 같은 객체를 반환합니다.

    💡 왜 캐싱하나요?
        Settings를 생성할 때마다 .env 파일을 읽으면 느립니다.
        한 번만 읽고 재사용하면 성능이 좋아집니다.

    Returns:
        Settings: 설정 인스턴스
    """
    return Settings()
