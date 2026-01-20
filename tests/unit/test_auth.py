import pytest
from httpx import AsyncClient
from fastapi import status

from app.utils.auth import verify_password, get_password_hash, create_access_token, decode_access_token


class TestAuthUtils:
    """인증 유틸리티 테스트"""
    
    def test_password_hashing(self):
        """비밀번호 해싱 테스트"""
        password = "testpass123!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrongpass", hashed)
    
    def test_jwt_token_creation_and_decode(self):
        """JWT 토큰 생성 및 디코딩 테스트"""
        data = {"sub": "123", "email": "test@example.com"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "123"
        assert decoded["email"] == "test@example.com"
        assert decoded["type"] == "access"
    
    def test_invalid_token_decode(self):
        """잘못된 토큰 디코딩 테스트"""
        invalid_token = "invalid.token.here"
        decoded = decode_access_token(invalid_token)
        assert decoded is None


class TestAuthAPI:
    """인증 API 테스트"""
    
    @pytest.mark.asyncio
    async def test_user_registration_success(self, client: AsyncClient):
        """사용자 회원가입 성공 테스트"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123!"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == user_data["username"]
        assert data["email"] == user_data["email"]
        assert "id" in data
        assert "password" not in data
    
    @pytest.mark.asyncio
    async def test_user_registration_duplicate_email(self, client: AsyncClient, test_user_1):
        """중복 이메일 회원가입 실패 테스트"""
        user_data = {
            "username": "newuser",
            "email": test_user_1.email,  # 이미 존재하는 이메일
            "password": "newpass123!"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already registered" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_user_registration_duplicate_username(self, client: AsyncClient, test_user_1):
        """중복 사용자명 회원가입 실패 테스트"""
        user_data = {
            "username": test_user_1.username,  # 이미 존재하는 사용자명
            "email": "newuser@example.com",
            "password": "newpass123!"
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already taken" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_user_registration_invalid_password(self, client: AsyncClient):
        """잘못된 비밀번호 형식 회원가입 실패 테스트"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "weak"  # 약한 비밀번호
        }
        
        response = await client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_user_login_success(self, client: AsyncClient, test_user_1):
        """사용자 로그인 성공 테스트"""
        login_data = {
            "email": test_user_1.email,
            "password": "testpass123!"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    @pytest.mark.asyncio
    async def test_user_login_invalid_email(self, client: AsyncClient):
        """존재하지 않는 이메일 로그인 실패 테스트"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "testpass123!"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_user_login_invalid_password(self, client: AsyncClient, test_user_1):
        """잘못된 비밀번호 로그인 실패 테스트"""
        login_data = {
            "email": test_user_1.email,
            "password": "wrongpassword"
        }
        
        response = await client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient, auth_token_user_1):
        """유효한 토큰으로 보호된 엔드포인트 접근 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get("/friends", headers=headers)
        
        # 친구 목록 조회는 성공해야 함 (빈 목록이라도)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """토큰 없이 보호된 엔드포인트 접근 실패 테스트"""
        response = await client.get("/friends")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_token(self, client: AsyncClient):
        """잘못된 토큰으로 보호된 엔드포인트 접근 실패 테스트"""
        headers = {"Authorization": "Bearer invalid.token.here"}
        
        response = await client.get("/friends", headers=headers)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED