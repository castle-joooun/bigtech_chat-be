"""
E2E Tests for User Service
"""

import pytest
import httpx
from typing import Dict, Any

from conftest import auth_headers


class TestHealthCheck:
    """Health check tests"""

    def test_health_endpoint(self, http_client: httpx.Client, user_service_url: str):
        """Test health endpoint returns 200"""
        response = http_client.get(f"{user_service_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"


class TestUserRegistration:
    """User registration tests"""

    def test_register_success(self, http_client: httpx.Client, user_service_url: str, test_user_data: Dict[str, Any]):
        """Test successful user registration"""
        response = http_client.post(
            f"{user_service_url}/api/auth/register",
            json=test_user_data
        )
        assert response.status_code == 201
        data = response.json()
        assert "user_id" in data or "id" in data
        assert data.get("email") == test_user_data["email"]

    def test_register_duplicate_email(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test registration with duplicate email fails"""
        response = http_client.post(
            f"{user_service_url}/api/auth/register",
            json={
                "email": registered_user["email"],
                "password": "AnotherPass123!",
                "nickname": "AnotherNickname"
            }
        )
        assert response.status_code in [400, 409]

    def test_register_invalid_email(self, http_client: httpx.Client, user_service_url: str):
        """Test registration with invalid email fails"""
        response = http_client.post(
            f"{user_service_url}/api/auth/register",
            json={
                "email": "invalid-email",
                "password": "TestPass123!",
                "nickname": "TestNickname"
            }
        )
        assert response.status_code == 422

    def test_register_weak_password(self, http_client: httpx.Client, user_service_url: str):
        """Test registration with weak password fails"""
        response = http_client.post(
            f"{user_service_url}/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "weak",
                "nickname": "TestNickname"
            }
        )
        assert response.status_code == 422


class TestUserAuthentication:
    """User authentication tests"""

    def test_login_success(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test successful login"""
        response = http_client.post(
            f"{user_service_url}/api/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("token_type") == "bearer"

    def test_login_wrong_password(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test login with wrong password fails"""
        response = http_client.post(
            f"{user_service_url}/api/auth/login",
            json={
                "email": registered_user["email"],
                "password": "WrongPassword123!"
            }
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, http_client: httpx.Client, user_service_url: str):
        """Test login with non-existent user fails"""
        response = http_client.post(
            f"{user_service_url}/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "TestPass123!"
            }
        )
        assert response.status_code in [401, 404]

    def test_logout_success(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test successful logout"""
        response = http_client.post(
            f"{user_service_url}/api/auth/logout",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code == 200


class TestUserProfile:
    """User profile tests"""

    def test_get_profile(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test getting user profile"""
        response = http_client.get(
            f"{user_service_url}/api/profile",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("email") == registered_user["email"]

    def test_get_profile_unauthorized(self, http_client: httpx.Client, user_service_url: str):
        """Test getting profile without auth fails"""
        response = http_client.get(f"{user_service_url}/api/profile")
        assert response.status_code in [401, 403]

    def test_update_profile(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test updating user profile"""
        new_nickname = "UpdatedNickname"
        response = http_client.patch(
            f"{user_service_url}/api/profile",
            headers=auth_headers(registered_user["access_token"]),
            json={"nickname": new_nickname}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("nickname") == new_nickname


class TestUserSearch:
    """User search tests"""

    def test_search_users(self, http_client: httpx.Client, user_service_url: str, registered_user: Dict[str, Any]):
        """Test searching for users"""
        response = http_client.get(
            f"{user_service_url}/api/users/search",
            headers=auth_headers(registered_user["access_token"]),
            params={"q": registered_user["nickname"][:4]}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "users" in data

    def test_search_users_unauthorized(self, http_client: httpx.Client, user_service_url: str):
        """Test searching without auth fails"""
        response = http_client.get(
            f"{user_service_url}/api/users/search",
            params={"q": "test"}
        )
        assert response.status_code in [401, 403]
