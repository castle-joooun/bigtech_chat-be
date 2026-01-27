"""
E2E Tests for Chat Service
"""

import pytest
import httpx
from typing import Dict, Any

from conftest import auth_headers


class TestHealthCheck:
    """Health check tests"""

    def test_health_endpoint(self, http_client: httpx.Client, chat_service_url: str):
        """Test health endpoint returns 200"""
        response = http_client.get(f"{chat_service_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"


class TestChatRoom:
    """Chat room tests"""

    def test_create_chat_room(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ):
        """Test creating a chat room"""
        response = http_client.post(
            f"{chat_service_url}/api/chat-rooms",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "name": "Test Chat Room",
                "participant_ids": [registered_user_2["user_id"]]
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "room_id" in data

    def test_create_chat_room_unauthorized(
        self,
        http_client: httpx.Client,
        chat_service_url: str
    ):
        """Test creating chat room without auth fails"""
        response = http_client.post(
            f"{chat_service_url}/api/chat-rooms",
            json={"name": "Test Room", "participant_ids": []}
        )
        assert response.status_code in [401, 403]

    def test_get_chat_rooms(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any]
    ):
        """Test getting user's chat rooms"""
        response = http_client.get(
            f"{chat_service_url}/api/chat-rooms",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "rooms" in data


class TestChatRoomOperations:
    """Chat room operation tests"""

    @pytest.fixture
    def chat_room(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a chat room fixture"""
        response = http_client.post(
            f"{chat_service_url}/api/chat-rooms",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "name": "Test Chat Room",
                "participant_ids": [registered_user_2["user_id"]]
            }
        )
        if response.status_code in [200, 201]:
            return response.json()
        return {"id": None, "room_id": None}

    def test_get_chat_room_by_id(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        chat_room: Dict[str, Any]
    ):
        """Test getting chat room by ID"""
        room_id = chat_room.get("id") or chat_room.get("room_id")
        if not room_id:
            pytest.skip("No chat room created")

        response = http_client.get(
            f"{chat_service_url}/api/chat-rooms/{room_id}",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code == 200

    def test_get_nonexistent_chat_room(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any]
    ):
        """Test getting non-existent chat room returns 404"""
        response = http_client.get(
            f"{chat_service_url}/api/chat-rooms/nonexistent-id-12345",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code == 404


class TestMessages:
    """Message tests"""

    @pytest.fixture
    def chat_room_with_id(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ) -> str:
        """Create a chat room and return its ID"""
        response = http_client.post(
            f"{chat_service_url}/api/chat-rooms",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "name": "Message Test Room",
                "participant_ids": [registered_user_2["user_id"]]
            }
        )
        if response.status_code in [200, 201]:
            data = response.json()
            return data.get("id") or data.get("room_id")
        return None

    def test_send_message(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        chat_room_with_id: str
    ):
        """Test sending a message"""
        if not chat_room_with_id:
            pytest.skip("No chat room created")

        response = http_client.post(
            f"{chat_service_url}/api/messages",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "room_id": chat_room_with_id,
                "content": "Hello, this is a test message!"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "message_id" in data

    def test_send_message_unauthorized(
        self,
        http_client: httpx.Client,
        chat_service_url: str
    ):
        """Test sending message without auth fails"""
        response = http_client.post(
            f"{chat_service_url}/api/messages",
            json={
                "room_id": "some-room-id",
                "content": "Test message"
            }
        )
        assert response.status_code in [401, 403]

    def test_get_messages(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        chat_room_with_id: str
    ):
        """Test getting messages from a chat room"""
        if not chat_room_with_id:
            pytest.skip("No chat room created")

        # Send a message first
        http_client.post(
            f"{chat_service_url}/api/messages",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "room_id": chat_room_with_id,
                "content": "Test message for retrieval"
            }
        )

        # Get messages
        response = http_client.get(
            f"{chat_service_url}/api/messages",
            headers=auth_headers(registered_user["access_token"]),
            params={"room_id": chat_room_with_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "messages" in data

    def test_get_messages_pagination(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        chat_room_with_id: str
    ):
        """Test message pagination"""
        if not chat_room_with_id:
            pytest.skip("No chat room created")

        response = http_client.get(
            f"{chat_service_url}/api/messages",
            headers=auth_headers(registered_user["access_token"]),
            params={
                "room_id": chat_room_with_id,
                "limit": 10,
                "offset": 0
            }
        )
        assert response.status_code == 200


class TestMessageOperations:
    """Message operation tests"""

    @pytest.fixture
    def message_data(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        registered_user_2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a message and return its data"""
        # Create room
        room_response = http_client.post(
            f"{chat_service_url}/api/chat-rooms",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "name": "Message Op Test Room",
                "participant_ids": [registered_user_2["user_id"]]
            }
        )

        if room_response.status_code not in [200, 201]:
            return {"room_id": None, "message_id": None}

        room_data = room_response.json()
        room_id = room_data.get("id") or room_data.get("room_id")

        # Create message
        msg_response = http_client.post(
            f"{chat_service_url}/api/messages",
            headers=auth_headers(registered_user["access_token"]),
            json={
                "room_id": room_id,
                "content": "Test message for operations"
            }
        )

        if msg_response.status_code in [200, 201]:
            msg_data = msg_response.json()
            return {
                "room_id": room_id,
                "message_id": msg_data.get("id") or msg_data.get("message_id")
            }
        return {"room_id": room_id, "message_id": None}

    def test_mark_messages_read(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user_2: Dict[str, Any],
        message_data: Dict[str, Any]
    ):
        """Test marking messages as read"""
        if not message_data.get("room_id"):
            pytest.skip("No room created")

        response = http_client.post(
            f"{chat_service_url}/api/messages/read",
            headers=auth_headers(registered_user_2["access_token"]),
            json={"room_id": message_data["room_id"]}
        )
        assert response.status_code == 200

    def test_delete_message(
        self,
        http_client: httpx.Client,
        chat_service_url: str,
        registered_user: Dict[str, Any],
        message_data: Dict[str, Any]
    ):
        """Test deleting a message"""
        if not message_data.get("message_id"):
            pytest.skip("No message created")

        response = http_client.delete(
            f"{chat_service_url}/api/messages/{message_data['message_id']}",
            headers=auth_headers(registered_user["access_token"])
        )
        assert response.status_code in [200, 204]
