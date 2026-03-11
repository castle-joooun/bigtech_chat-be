"""
=============================================================================
Service Registry - 서비스 등록 및 라우팅
=============================================================================

📌 이 파일이 하는 일:
    API Gateway가 요청을 어느 서비스로 보낼지 결정하는 "주소록"입니다.
    마치 전화번호부에서 이름으로 전화번호를 찾는 것처럼,
    URL 경로로 백엔드 서비스를 찾습니다.

🔍 라우팅 예시:
    /api/auth/login     → user-service:8005
    /api/friends/list   → friend-service:8003
    /api/messages/send  → chat-service:8002

💡 왜 레지스트리가 필요한가요?
    1. 중앙 관리: 서비스 주소를 한 곳에서 관리
    2. 유연성: 서비스 주소가 바뀌면 여기만 수정하면 됨
    3. 확장성: 새 서비스 추가가 쉬움

📊 현재 등록된 서비스:
    - user-service (8005): 사용자 인증, 프로필
    - friend-service (8003): 친구 관계 관리
    - chat-service (8002): 채팅방, 메시지
"""

from typing import Dict, Optional
from dataclasses import dataclass
from .config import get_settings


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class ServiceInfo:
    """
    📌 서비스 정보를 담는 클래스

    마이크로서비스 하나의 정보를 담고 있습니다.

    Attributes:
        name: 서비스 이름 (예: "user-service")
        url: 서비스 접속 URL (예: "http://user-service:8005")
        timeout: 요청 타임아웃 (초 단위, 기본 30초)
                 30초 동안 응답이 없으면 실패 처리
    """
    name: str
    url: str
    timeout: float = 30.0


# =============================================================================
# 서비스 레지스트리 클래스
# =============================================================================

class ServiceRegistry:
    """
    📌 서비스 레지스트리 (서비스 주소록)

    모든 마이크로서비스의 정보를 관리하고,
    요청 URL을 보고 어느 서비스로 보낼지 결정합니다.

    사용 예시:
        registry = get_registry()
        service = registry.resolve_route("/api/auth/login")
        # → user-service 정보 반환
    """

    def __init__(self):
        """
        레지스트리 초기화

        환경 설정에서 각 서비스의 URL을 가져와서 등록합니다.
        """
        settings = get_settings()

        # =====================================================================
        # 서비스 정의
        # =====================================================================
        # 각 서비스의 이름, URL, 타임아웃을 정의합니다
        self._services: Dict[str, ServiceInfo] = {
            # user-service: 사용자 관련 모든 기능
            # - 회원가입, 로그인, 로그아웃
            # - 프로필 조회/수정
            # - 사용자 검색
            "user": ServiceInfo(
                name="user-service",
                url=settings.user_service_url,  # 기본값: http://user-service:8005
                timeout=settings.default_timeout
            ),

            # friend-service: 친구 관계 관리
            # - 친구 요청 보내기/받기
            # - 친구 목록 조회
            # - 친구 삭제, 차단
            "friend": ServiceInfo(
                name="friend-service",
                url=settings.friend_service_url,  # 기본값: http://friend-service:8003
                timeout=settings.default_timeout
            ),

            # chat-service: 채팅 기능
            # - 채팅방 생성/조회
            # - 메시지 전송/조회
            "chat": ServiceInfo(
                name="chat-service",
                url=settings.chat_service_url,  # 기본값: http://chat-service:8002
                timeout=settings.default_timeout
            )
        }

        # =====================================================================
        # 라우팅 규칙: URL 경로 → 서비스 키
        # =====================================================================
        # 클라이언트 요청 URL을 보고 어느 서비스로 보낼지 결정합니다
        #
        # 예시:
        #   클라이언트가 /api/auth/login 요청 →
        #   "/api/auth"로 시작하므로 → "user" 서비스로 전달
        self._routes: Dict[str, str] = {
            # 사용자 서비스 라우팅
            "/api/auth": "user",      # 로그인, 회원가입, 토큰 갱신
            "/api/profile": "user",   # 프로필 조회/수정
            "/api/users": "user",     # 사용자 검색

            # 친구 서비스 라우팅
            "/api/friends": "friend",  # 친구 목록, 요청, 삭제

            # 채팅 서비스 라우팅
            "/api/chat-rooms": "chat",  # 채팅방 CRUD
            "/api/messages": "chat",    # 메시지 전송/조회
        }

    def get_service(self, service_key: str) -> Optional[ServiceInfo]:
        """
        📌 서비스 키로 서비스 정보 조회

        Args:
            service_key: 서비스 키 (예: "user", "friend", "chat")

        Returns:
            ServiceInfo 또는 None (없는 키면)

        예시:
            service = registry.get_service("user")
            # → ServiceInfo(name="user-service", url="http://...", timeout=30.0)
        """
        return self._services.get(service_key)

    def resolve_route(self, path: str) -> Optional[ServiceInfo]:
        """
        📌 요청 경로에서 대상 서비스 결정

        클라이언트의 요청 URL을 분석해서 어느 서비스로 보낼지 결정합니다.
        라우팅 규칙(self._routes)을 순회하면서 매칭되는 것을 찾습니다.

        Args:
            path: 요청 경로 (예: /api/auth/login)

        Returns:
            ServiceInfo 또는 None (매칭되는 라우팅 규칙이 없으면)

        예시:
            # /api/auth/login → user-service로 라우팅
            service = registry.resolve_route("/api/auth/login")
            print(service.name)  # "user-service"
            print(service.url)   # "http://user-service:8005"

            # /api/unknown → None (매칭 안 됨)
            service = registry.resolve_route("/api/unknown")
            print(service)  # None
        """
        # 등록된 모든 라우팅 규칙을 순회
        for route_prefix, service_key in self._routes.items():
            # 요청 경로가 라우팅 prefix로 시작하는지 확인
            # 예: "/api/auth/login".startswith("/api/auth") → True
            if path.startswith(route_prefix):
                return self._services.get(service_key)

        # 매칭되는 규칙이 없으면 None 반환
        return None

    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """
        📌 모든 서비스 정보 반환

        헬스 체크 등에서 모든 서비스 목록이 필요할 때 사용합니다.

        Returns:
            dict: 서비스 키 → ServiceInfo 매핑 복사본
        """
        return self._services.copy()


# =============================================================================
# 싱글톤 패턴
# =============================================================================
# 레지스트리는 애플리케이션 전체에서 하나만 있으면 됩니다.
# 매번 새로 만들지 않고, 한 번 만들어서 재사용합니다.

_registry: Optional[ServiceRegistry] = None


def get_registry() -> ServiceRegistry:
    """
    📌 레지스트리 싱글톤 반환

    처음 호출 시 레지스트리를 생성하고,
    이후에는 이미 만들어진 것을 반환합니다.

    Returns:
        ServiceRegistry: 싱글톤 레지스트리 인스턴스

    💡 싱글톤 패턴이란?
        객체를 딱 하나만 만들어서 공유하는 패턴입니다.
        - 메모리 절약
        - 일관된 상태 유지
    """
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
