"""
E2E Test Configuration and Fixtures
"""

import os
import pytest
import httpx
from typing import Generator, Dict, Any

# Service URLs
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8005")
FRIEND_SERVICE_URL = os.getenv("FRIEND_SERVICE_URL", "http://localhost:8003")
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8002")


@pytest.fixture(scope="session")
def user_service_url() -> str:
    return USER_SERVICE_URL


@pytest.fixture(scope="session")
def friend_service_url() -> str:
    return FRIEND_SERVICE_URL


@pytest.fixture(scope="session")
def chat_service_url() -> str:
    return CHAT_SERVICE_URL


@pytest.fixture(scope="session")
def http_client() -> Generator[httpx.Client, None, None]:
    """Shared HTTP client for all tests"""
    with httpx.Client(timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def async_http_client() -> Generator[httpx.AsyncClient, None, None]:
    """Shared async HTTP client for all tests"""
    import asyncio
    client = httpx.AsyncClient(timeout=30.0)
    yield client
    asyncio.get_event_loop().run_until_complete(client.aclose())


@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Generate unique test user data"""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return {
        "email": f"testuser_{unique_id}@example.com",
        "password": "TestPass123!",
        "nickname": f"TestUser_{unique_id}"
    }


@pytest.fixture
def test_user_data_2() -> Dict[str, Any]:
    """Generate second unique test user data"""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return {
        "email": f"testuser2_{unique_id}@example.com",
        "password": "TestPass123!",
        "nickname": f"TestUser2_{unique_id}"
    }


@pytest.fixture
def registered_user(http_client: httpx.Client, user_service_url: str, test_user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a user and return user data with token"""
    # Register
    response = http_client.post(
        f"{user_service_url}/api/auth/register",
        json=test_user_data
    )
    assert response.status_code == 201, f"Registration failed: {response.text}"

    # Login
    login_response = http_client.post(
        f"{user_service_url}/api/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        }
    )
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"

    login_data = login_response.json()
    return {
        **test_user_data,
        "user_id": login_data.get("user_id"),
        "access_token": login_data.get("access_token")
    }


@pytest.fixture
def registered_user_2(http_client: httpx.Client, user_service_url: str, test_user_data_2: Dict[str, Any]) -> Dict[str, Any]:
    """Register a second user and return user data with token"""
    # Register
    response = http_client.post(
        f"{user_service_url}/api/auth/register",
        json=test_user_data_2
    )
    assert response.status_code == 201, f"Registration failed: {response.text}"

    # Login
    login_response = http_client.post(
        f"{user_service_url}/api/auth/login",
        json={
            "email": test_user_data_2["email"],
            "password": test_user_data_2["password"]
        }
    )
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"

    login_data = login_response.json()
    return {
        **test_user_data_2,
        "user_id": login_data.get("user_id"),
        "access_token": login_data.get("access_token")
    }


def auth_headers(access_token: str) -> Dict[str, str]:
    """Generate authorization headers"""
    return {"Authorization": f"Bearer {access_token}"}
