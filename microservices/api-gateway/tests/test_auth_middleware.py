"""
=============================================================================
Authentication Middleware Tests - Pure ASGI 인증 미들웨어 테스트
=============================================================================

테스트 항목:
    1. 공개 경로 접근 (토큰 없이 접근 가능)
    2. 보호된 경로 - 토큰 없음 (401 반환)
    3. 보호된 경로 - 유효한 토큰 (통과)
    4. 보호된 경로 - 유효하지 않은 토큰 (401 반환)
    5. 선택적 인증 경로 - 토큰 없이 접근 가능
    6. POST 요청 - body 보존 확인 (핵심 테스트)
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ASGITransport

from app.auth.middleware import AuthenticationMiddleware
from app.config import get_settings


# =============================================================================
# 테스트 설정
# =============================================================================

settings = get_settings()


def create_test_token(
    user_id: str = "123",
    email: str = "test@example.com",
    username: str = "testuser",
    expired: bool = False,
    token_type: str = "access"
) -> str:
    """테스트용 JWT 토큰 생성"""
    if expired:
        exp = datetime.utcnow() - timedelta(hours=1)
    else:
        exp = datetime.utcnow() + timedelta(hours=1)

    payload = {
        "sub": user_id,
        "email": email,
        "username": username,
        "type": token_type,
        "exp": exp
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def create_test_app() -> FastAPI:
    """테스트용 FastAPI 앱 생성"""
    app = FastAPI()

    # 인증 미들웨어 추가
    app.add_middleware(AuthenticationMiddleware)

    # 공개 경로
    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/api/auth/login")
    async def login(request: Request):
        body = await request.json()
        return {"message": "login", "body": body}

    # 보호된 경로
    @app.get("/api/users/me")
    async def get_me(request: Request):
        user = request.state.user
        authenticated = request.state.authenticated
        return {
            "user_id": user.user_id if user else None,
            "authenticated": authenticated
        }

    @app.post("/api/messages")
    async def create_message(request: Request):
        """POST 요청 body 보존 테스트"""
        body = await request.json()
        user = request.state.user
        return {
            "user_id": user.user_id if user else None,
            "body": body
        }

    # 선택적 인증 경로
    @app.get("/api/users/search")
    async def search_users(request: Request):
        user = request.state.user
        authenticated = request.state.authenticated
        return {
            "user_id": user.user_id if user else None,
            "authenticated": authenticated
        }

    return app


@pytest.fixture
def app():
    return create_test_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# 테스트 케이스
# =============================================================================

class TestPublicPaths:
    """공개 경로 테스트"""

    @pytest.mark.asyncio
    async def test_health_without_token(self, client):
        """토큰 없이 /health 접근 가능"""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_login_without_token(self, client):
        """토큰 없이 /api/auth/login 접근 가능"""
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "login"


class TestProtectedPaths:
    """보호된 경로 테스트"""

    @pytest.mark.asyncio
    async def test_protected_path_without_token(self, client):
        """토큰 없이 보호된 경로 접근 시 401"""
        response = await client.get("/api/users/me")
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"
        assert "Missing" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_protected_path_with_valid_token(self, client):
        """유효한 토큰으로 보호된 경로 접근"""
        token = create_test_token(user_id="456")
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "456"
        assert response.json()["authenticated"] is True

    @pytest.mark.asyncio
    async def test_protected_path_with_expired_token(self, client):
        """만료된 토큰으로 보호된 경로 접근 시 401"""
        token = create_test_token(expired=True)
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_protected_path_with_invalid_token(self, client):
        """유효하지 않은 토큰으로 보호된 경로 접근 시 401"""
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_protected_path_with_wrong_token_type(self, client):
        """refresh 토큰으로 보호된 경로 접근 시 401"""
        token = create_test_token(token_type="refresh")
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"


class TestOptionalAuthPaths:
    """선택적 인증 경로 테스트"""

    @pytest.mark.asyncio
    async def test_optional_path_without_token(self, client):
        """토큰 없이 선택적 인증 경로 접근 가능"""
        response = await client.get("/api/users/search")
        assert response.status_code == 200
        assert response.json()["user_id"] is None
        assert response.json()["authenticated"] is False

    @pytest.mark.asyncio
    async def test_optional_path_with_valid_token(self, client):
        """유효한 토큰으로 선택적 인증 경로 접근"""
        token = create_test_token(user_id="789")
        response = await client.get(
            "/api/users/search",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "789"
        assert response.json()["authenticated"] is True

    @pytest.mark.asyncio
    async def test_optional_path_with_invalid_token(self, client):
        """유효하지 않은 토큰으로 선택적 인증 경로 접근 - 비인증 상태로 통과"""
        response = await client.get(
            "/api/users/search",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 200
        assert response.json()["user_id"] is None
        assert response.json()["authenticated"] is False


class TestBodyPreservation:
    """
    📌 핵심 테스트: POST 요청 body 보존

    BaseHTTPMiddleware의 버그로 인해 body가 소비되는 문제를 해결했는지 확인
    """

    @pytest.mark.asyncio
    async def test_post_body_preserved_with_token(self, client):
        """POST 요청 body가 보존되는지 확인 (인증 성공)"""
        token = create_test_token(user_id="123")
        message_data = {
            "room_id": "room_456",
            "content": "Hello, World!",
            "type": "text"
        }

        response = await client.post(
            "/api/messages",
            json=message_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["user_id"] == "123"
        # body가 보존되어야 함
        assert result["body"]["room_id"] == "room_456"
        assert result["body"]["content"] == "Hello, World!"
        assert result["body"]["type"] == "text"

    @pytest.mark.asyncio
    async def test_post_body_preserved_on_login(self, client):
        """로그인 요청 body가 보존되는지 확인 (공개 경로)"""
        login_data = {
            "email": "user@example.com",
            "password": "secure_password_123"
        }

        response = await client.post(
            "/api/auth/login",
            json=login_data
        )

        assert response.status_code == 200
        result = response.json()
        # body가 보존되어야 함
        assert result["body"]["email"] == "user@example.com"
        assert result["body"]["password"] == "secure_password_123"

    @pytest.mark.asyncio
    async def test_large_post_body_preserved(self, client):
        """큰 POST body도 보존되는지 확인"""
        token = create_test_token(user_id="123")
        large_content = "A" * 10000  # 10KB 문자열

        response = await client.post(
            "/api/messages",
            json={"content": large_content},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["body"]["content"] == large_content


class TestAuthorizationHeaderFormats:
    """Authorization 헤더 형식 테스트"""

    @pytest.mark.asyncio
    async def test_bearer_lowercase(self, client):
        """bearer (소문자)도 허용"""
        token = create_test_token(user_id="123")
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"bearer {token}"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bearer_uppercase(self, client):
        """BEARER (대문자)도 허용"""
        token = create_test_token(user_id="123")
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"BEARER {token}"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_basic_auth_rejected(self, client):
        """Basic 인증은 거부"""
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_header(self, client):
        """잘못된 형식의 헤더 거부"""
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401
