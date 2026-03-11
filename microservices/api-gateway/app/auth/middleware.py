"""
=============================================================================
Authentication Middleware - Pure ASGI JWT 인증 미들웨어
=============================================================================

📌 이 파일이 하는 일:
    모든 API 요청에서 JWT 토큰을 검증하고,
    인증된 사용자 정보를 백엔드 서비스에 전달합니다.

🔄 인증 흐름:
    1. 클라이언트가 요청에 Authorization 헤더 포함
       Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR...
    2. 미들웨어가 토큰을 추출하고 검증
    3. 유효하면 사용자 정보를 request.state에 저장
    4. 백엔드 서비스로 요청 전달 시 X-User-* 헤더 추가

💡 공개 경로와 인증 필수 경로:
    - 공개 경로: 로그인 없이 접근 가능 (/api/auth/login 등)
    - 인증 필수 경로: 토큰 없으면 401 에러
    - 선택적 인증 경로: 토큰 없어도 되지만, 있으면 추가 기능 사용 가능

✅ Pure ASGI 구현:
    BaseHTTPMiddleware의 request body 소비 버그를 해결하기 위해
    저수준 ASGI 인터페이스를 직접 구현합니다.

    BaseHTTPMiddleware 문제점:
        - 내부적으로 request.body()를 호출하면 스트림이 소비됨
        - 이후 프록시에서 body를 다시 읽을 수 없음

    Pure ASGI 해결책:
        - receive 함수를 가로채지 않고 그대로 전달
        - body를 읽지 않고 헤더만 검사
        - scope에 사용자 정보 저장
"""

import json
import logging
from typing import Optional, Callable, Awaitable

from .jwt import decode_access_token, JWTPayload


logger = logging.getLogger("api-gateway.auth")


# =============================================================================
# 경로 분류
# =============================================================================

# 인증이 필요 없는 공개 경로
# 로그인, 회원가입 등 인증 전에 사용하는 API
PUBLIC_PATHS = [
    "/health",            # 서버 상태 확인 (모니터링용)
    "/health/services",   # 서비스 상태 확인
    "/health/circuits",   # Circuit Breaker 상태
    "/metrics",           # Prometheus 메트릭
    "/docs",              # Swagger UI (API 문서)
    "/redoc",             # ReDoc (API 문서)
    "/openapi.json",      # OpenAPI 스펙
    "/api/auth/login",    # 로그인
    "/api/auth/register", # 회원가입
    "/api/auth/refresh",  # 토큰 갱신
]

# 인증이 선택적인 경로
# 로그인 안 해도 기본 기능은 사용 가능
# 로그인 하면 추가 기능(예: 친구 표시) 제공
OPTIONAL_AUTH_PATHS = [
    "/api/users/search",  # 사용자 검색 (비로그인: 기본 정보만)
]


# =============================================================================
# Pure ASGI 인증 미들웨어
# =============================================================================

class AuthenticationMiddleware:
    """
    📌 Pure ASGI 인증 미들웨어

    BaseHTTPMiddleware를 사용하지 않고 ASGI 인터페이스를 직접 구현합니다.
    이렇게 하면 request body를 소비하지 않아 프록시에서 body를 읽을 수 있습니다.

    🔄 ASGI 동작 방식:
        1. __call__(scope, receive, send) 호출됨
        2. scope: 요청 정보 (경로, 헤더 등)
        3. receive: body를 읽는 함수 (스트림)
        4. send: 응답을 보내는 함수

    💡 핵심 포인트:
        - receive를 호출하지 않으면 body가 소비되지 않음
        - 헤더만 검사하고, body는 그대로 다음 앱에 전달
        - scope["state"]에 사용자 정보 저장
    """

    def __init__(self, app):
        """
        Args:
            app: 다음 ASGI 앱 (FastAPI 또는 다음 미들웨어)
        """
        self.app = app

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]]
    ) -> None:
        """
        📌 ASGI 엔트리포인트

        모든 요청이 이 함수를 통과합니다.

        Args:
            scope: 요청 메타데이터 (type, path, headers, state 등)
            receive: 요청 body를 읽는 비동기 함수
            send: 응답을 보내는 비동기 함수
        """
        # HTTP 요청이 아니면 그대로 통과 (WebSocket 등)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 경로 추출
        path = scope.get("path", "")

        # scope에 state가 없으면 생성
        if "state" not in scope:
            scope["state"] = {}

        # =====================================================================
        # Step 1: 공개 경로 확인
        # =====================================================================
        if self._is_public_path(path):
            scope["state"]["user"] = None
            scope["state"]["authenticated"] = False
            await self.app(scope, receive, send)
            return

        # =====================================================================
        # Step 2: Authorization 헤더에서 토큰 추출
        # =====================================================================
        token = self._extract_token_from_scope(scope)

        # =====================================================================
        # Step 3: 토큰 유무에 따른 처리
        # =====================================================================
        if not token:
            if self._is_optional_auth_path(path):
                # 선택적 인증 경로면 비인증 상태로 통과
                scope["state"]["user"] = None
                scope["state"]["authenticated"] = False
                await self.app(scope, receive, send)
                return

            # 필수 인증 경로면 401 Unauthorized 반환
            await self._send_unauthorized(send, "Missing authentication token")
            return

        # =====================================================================
        # Step 4: JWT 토큰 검증
        # =====================================================================
        payload = decode_access_token(token)

        if not payload:
            if self._is_optional_auth_path(path):
                # 선택적 인증 경로면 비인증 상태로 통과
                scope["state"]["user"] = None
                scope["state"]["authenticated"] = False
                await self.app(scope, receive, send)
                return

            await self._send_unauthorized(send, "Invalid or expired token")
            return

        # =====================================================================
        # Step 5: 인증 성공 - 사용자 정보 저장
        # =====================================================================
        # scope["state"]에 저장하면 request.state로 접근 가능
        scope["state"]["user"] = payload
        scope["state"]["authenticated"] = True

        logger.debug(f"Authenticated user: {payload.user_id}")

        # 다음 앱 호출 (receive를 그대로 전달 → body 보존)
        await self.app(scope, receive, send)

    def _is_public_path(self, path: str) -> bool:
        """
        📌 공개 경로 확인

        인증 없이 접근 가능한 경로인지 확인합니다.
        """
        for public_path in PUBLIC_PATHS:
            if path == public_path or path.startswith(public_path + "/"):
                return True
        return False

    def _is_optional_auth_path(self, path: str) -> bool:
        """
        📌 선택적 인증 경로 확인
        """
        for optional_path in OPTIONAL_AUTH_PATHS:
            if path == optional_path or path.startswith(optional_path + "/"):
                return True
        return False

    def _extract_token_from_scope(self, scope: dict) -> Optional[str]:
        """
        📌 ASGI scope에서 Bearer 토큰 추출

        헤더 형식: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

        ASGI에서 헤더는 (name, value) 튜플의 리스트로 저장됩니다.
        예: [(b"authorization", b"Bearer xxx"), (b"content-type", b"application/json")]
        """
        headers = scope.get("headers", [])

        for name, value in headers:
            # 헤더 이름은 바이트로 저장됨
            if name.lower() == b"authorization":
                # 값도 바이트이므로 디코드
                auth_header = value.decode("utf-8")
                parts = auth_header.split()

                if len(parts) == 2 and parts[0].lower() == "bearer":
                    return parts[1]

        return None

    async def _send_unauthorized(
        self,
        send: Callable[[dict], Awaitable[None]],
        message: str
    ) -> None:
        """
        📌 401 Unauthorized 응답 전송

        ASGI 프로토콜에 따라 응답을 보냅니다.
        1. http.response.start: 상태 코드와 헤더
        2. http.response.body: 응답 본문

        Args:
            send: ASGI send 함수
            message: 에러 메시지
        """
        body = json.dumps({
            "error": "unauthorized",
            "message": message
        }).encode("utf-8")

        # HTTP 응답 시작 (상태 코드 + 헤더)
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("utf-8")),
            ],
        })

        # HTTP 응답 본문
        await send({
            "type": "http.response.body",
            "body": body,
        })
