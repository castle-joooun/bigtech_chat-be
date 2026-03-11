"""
E2E Tests for Friend Service
"""

import pytest
import httpx
from typing import Dict, Any

from conftest import auth_headers


class TestHealthCheck:
    """Health check tests"""

    def test_health_endpoint(self, http_client: httpx.Client, friend_service_url: str):
        """Test health endpoint returns 200"""
        response = http_client.get(f"{friend_service_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"


class TestFriendRequest:
    """Friend request tests"""

    def test_send_friend_request(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ):
        """Test sending a friend request"""
        response = http_client.post(
            f"{friend_service_url}/api/friends/request",
            headers=auth_headers(registered_user["access_token"]),
            json={"to_user_id": registered_user_2["user_id"]}
        )
        assert response.status_code in [200, 201]

    def test_send_friend_request_to_self(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user: Dict[str, Any]
    ):
        """Test sending friend request to self fails"""
        response = http_client.post(
            f"{friend_service_url}/api/friends/request",
            headers=auth_headers(registered_user["access_token"]),
            json={"to_user_id": registered_user["user_id"]}
        )
        assert response.status_code == 400

    def test_send_friend_request_unauthorized(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user_2: Dict[str, Any]
    ):
        """Test sending friend request without auth fails"""
        response = http_client.post(
            f"{friend_service_url}/api/friends/request",
            json={"to_user_id": registered_user_2["user_id"]}
        )
        assert response.status_code in [401, 403]


class TestFriendRequestManagement:
    """Friend request management tests"""

    @pytest.fixture
    def friend_request(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a friend request fixture"""
        response = http_client.post(
            f"{friend_service_url}/api/friends/request",
            headers=auth_headers(registered_user["access_token"]),
            json={"to_user_id": registered_user_2["user_id"]}
        )
        if response.status_code in [200, 201]:
            return response.json()
        return {"request_id": None}

    def test_get_pending_requests(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user_2: Dict[str, Any],
        friend_request: Dict[str, Any]
    ):
        """Test getting pending friend requests"""
        response = http_client.get(
            f"{friend_service_url}/api/friends/requests/pending",
            headers=auth_headers(registered_user_2["access_token"])
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "requests" in data

    def test_accept_friend_request(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user_2: Dict[str, Any],
        friend_request: Dict[str, Any]
    ):
        """Test accepting a friend request"""
        if not friend_request.get("request_id"):
            pytest.skip("No friend request created")

        response = http_client.post(
            f"{friend_service_url}/api/friends/{friend_request['request_id']}/accept",
            headers=auth_headers(registered_user_2["access_token"])
        )
        assert response.status_code == 200

    def test_reject_friend_request(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ):
        """Test rejecting a friend request"""
        # Create new request
        create_response = http_client.post(
            f"{friend_service_url}/api/friends/request",
            headers=auth_headers(registered_user["access_token"]),
            json={"to_user_id": registered_user_2["user_id"]}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Could not create friend request")

        request_data = create_response.json()
        request_id = request_data.get("request_id") or request_data.get("id")

        if not request_id:
            pytest.skip("No request_id in response")

        response = http_client.post(
            f"{friend_service_url}/api/friends/{request_id}/reject",
            headers=auth_headers(registered_user_2["access_token"])
        )
        assert response.status_code == 200


class TestFriendList:
    """Friend list tests"""

    def test_get_friends_list(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user: Dict[str, Any]
    ):
        """Test getting friends list"""
        response = http_client.get(
            f"{friend_service_url}/api/friends",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "friends" in data

    def test_get_friends_list_unauthorized(
        self,
        http_client: httpx.Client,
        friend_service_url: str
    ):
        """Test getting friends list without auth fails"""
        response = http_client.get(f"{friend_service_url}/api/friends")
        assert response.status_code in [401, 403]

    def test_search_friends(
        self,
        http_client: httpx.Client,
        friend_service_url: str,
        registered_user: Dict[str, Any]
    ):
        """Test searching friends"""
        response = http_client.get(
            f"{friend_service_url}/api/friends/search",
            headers=auth_headers(registered_user["access_token"]),
            params={"q": "test"}
        )
        assert response.status_code == 200
