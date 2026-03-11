"""
=============================================================================
HTTP Client - 백엔드 서비스 통신 클라이언트
=============================================================================

📌 이 파일이 하는 일:
    API Gateway가 백엔드 서비스(user-service, chat-service 등)와
    통신할 때 사용하는 HTTP 클라이언트를 관리합니다.

💡 왜 HTTPX를 사용하나요?
    - 비동기(async) 지원으로 빠른 처리
    - 연결 풀(Connection Pool)로 성능 최적화
    - HTTP/2 지원

🔄 연결 풀이란?
    매 요청마다 새로운 연결을 만들면 느립니다.
    연결을 미리 만들어놓고 재사용하면 빠릅니다.

    연결 풀 없이:
        요청1 → [연결 생성] → [요청] → [연결 종료]
        요청2 → [연결 생성] → [요청] → [연결 종료]

    연결 풀 사용:
        [미리 연결 생성]
        요청1 → [요청] (기존 연결 사용)
        요청2 → [요청] (기존 연결 사용)

📊 설정 값:
    - max_connections: 100 (동시에 열어둘 최대 연결 수)
    - max_keepalive_connections: 20 (대기 상태로 유지할 연결 수)
    - keepalive_expiry: 30초 (사용 안 하면 연결 종료)
"""

import httpx
from typing import Optional

from ..config import get_settings


# =============================================================================
# 전역 HTTP 클라이언트
# =============================================================================
# 애플리케이션 전체에서 하나의 클라이언트를 공유합니다 (싱글톤)

_http_client: Optional[httpx.AsyncClient] = None


# =============================================================================
# 클라이언트 생명주기 함수
# =============================================================================

async def init_http_client() -> httpx.AsyncClient:
    """
    📌 HTTP 클라이언트 초기화

    애플리케이션 시작 시(main.py의 lifespan) 한 번 호출됩니다.
    연결 풀을 설정하고 클라이언트를 생성합니다.

    Returns:
        httpx.AsyncClient: 초기화된 HTTP 클라이언트

    💡 타임아웃 설정:
        - connect: 5초 (서버 연결까지 대기)
        - read: 30초 (응답 읽기까지 대기)
        - write: 30초 (요청 전송까지 대기)
        - pool: 5초 (연결 풀에서 연결 대기)
    """
    global _http_client

    # 이미 초기화되어 있으면 기존 것 반환
    if _http_client is not None:
        return _http_client

    settings = get_settings()

    # HTTPX AsyncClient 생성
    _http_client = httpx.AsyncClient(
        # 타임아웃 설정 (초 단위)
        timeout=httpx.Timeout(
            connect=5.0,                      # 연결 타임아웃
            read=settings.default_timeout,    # 읽기 타임아웃 (기본 30초)
            write=settings.default_timeout,   # 쓰기 타임아웃
            pool=5.0                          # 연결 풀 대기 타임아웃
        ),
        # 연결 풀 설정
        limits=httpx.Limits(
            max_keepalive_connections=20,  # 대기 연결 최대 수
            max_connections=100,           # 전체 연결 최대 수
            keepalive_expiry=30.0          # 대기 연결 만료 시간 (초)
        ),
        follow_redirects=True  # 리다이렉트 자동 따라가기
    )

    return _http_client


async def close_http_client() -> None:
    """
    📌 HTTP 클라이언트 종료

    애플리케이션 종료 시(main.py의 lifespan) 호출됩니다.
    열려있는 모든 연결을 정리합니다.

    ⚠️ 주의:
        이 함수를 호출하지 않으면 연결이 남아있어
        리소스 누수(Resource Leak)가 발생할 수 있습니다.
    """
    global _http_client

    if _http_client is not None:
        # 모든 연결 닫기
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    """
    📌 HTTP 클라이언트 인스턴스 반환

    프록시 라우터 등에서 백엔드 서비스에 요청을 보낼 때 호출합니다.

    Returns:
        httpx.AsyncClient: 초기화된 HTTP 클라이언트

    Raises:
        RuntimeError: 클라이언트가 초기화되지 않은 경우
                     (init_http_client()를 먼저 호출해야 함)

    사용 예시:
        client = get_http_client()
        response = await client.get("http://user-service:8005/health")
    """
    if _http_client is None:
        raise RuntimeError(
            "HTTP client not initialized. Call init_http_client() first."
        )
    return _http_client
