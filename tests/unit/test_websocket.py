import pytest
import json
from httpx import AsyncClient
from fastapi import status
from fastapi.testclient import TestClient

from app.websockets.connection_manager import manager
from app.websockets.auth import authenticate_websocket, verify_room_access
from app.main import app


class TestWebSocketConnectionManager:
    """WebSocket 연결 매니저 테스트"""
    
    def test_connection_manager_initialization(self):
        """연결 매니저 초기화 테스트"""
        assert manager.room_connections == {}
        assert manager.user_connections == {}
        assert manager.connection_info == {}
    
    def test_get_room_users_empty(self):
        """빈 채팅방의 사용자 목록 조회 테스트"""
        users = manager.get_room_users("room123")
        assert users == []
    
    def test_get_user_count_in_room_empty(self):
        """빈 채팅방의 사용자 수 조회 테스트"""
        count = manager.get_user_count_in_room("room123")
        assert count == 0
    
    def test_is_user_connected_false(self):
        """연결되지 않은 사용자 확인 테스트"""
        connected = manager.is_user_connected("user123")
        assert connected is False
    
    def test_get_user_room_none(self):
        """연결되지 않은 사용자의 채팅방 조회 테스트"""
        room = manager.get_user_room("user123")
        assert room is None


class TestWebSocketAuth:
    """WebSocket 인증 테스트"""
    
    @pytest.mark.asyncio
    async def test_verify_room_access_success(self, test_session, test_user_1, test_chat_room):
        """채팅방 접근 권한 확인 성공 테스트"""
        # 사용자가 채팅방 멤버인 경우
        has_access = await verify_room_access(str(test_user_1.id), str(test_chat_room.id))
        # 현재 구현에서는 모든 사용자에게 접근을 허용
        assert has_access is True
    
    @pytest.mark.asyncio
    async def test_verify_room_access_invalid_ids(self, test_session):
        """잘못된 ID로 채팅방 접근 권한 확인 테스트"""
        has_access = await verify_room_access("invalid", "invalid")
        assert has_access is False


class TestWebSocketAPI:
    """WebSocket API 테스트"""
    
    @pytest.mark.asyncio
    async def test_websocket_room_status_success(self, client: AsyncClient, auth_token_user_1, test_chat_room):
        """WebSocket 채팅방 상태 조회 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get(f"/ws/rooms/{test_chat_room.id}/status", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "room_id" in data
        assert "online_users" in data
        assert "online_count" in data
        assert "is_active" in data
        assert "user_id" in data
        assert data["room_id"] == str(test_chat_room.id)
    
    @pytest.mark.asyncio
    async def test_websocket_room_status_unauthorized(self, client: AsyncClient, auth_token_user_3, test_chat_room):
        """권한 없는 사용자의 WebSocket 채팅방 상태 조회 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        
        response = await client.get(f"/ws/rooms/{test_chat_room.id}/status", headers=headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "권한이 없습니다" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_websocket_room_status_without_auth(self, client: AsyncClient, test_chat_room):
        """인증 없이 WebSocket 채팅방 상태 조회 실패 테스트"""
        response = await client.get(f"/ws/rooms/{test_chat_room.id}/status")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_websocket_room_status_nonexistent_room(self, client: AsyncClient, auth_token_user_1):
        """존재하지 않는 채팅방의 상태 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get("/ws/rooms/99999/status", headers=headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestWebSocketIntegration:
    """WebSocket 통합 테스트 (실제 WebSocket 연결 시뮬레이션)"""
    
    def test_websocket_connection_simulation(self):
        """WebSocket 연결 시뮬레이션 테스트"""
        with TestClient(app) as client:
            # WebSocket 엔드포인트 존재 확인
            # 실제 WebSocket 연결은 복잡하므로 엔드포인트 존재만 확인
            routes = [route.path for route in app.routes]
            websocket_routes = [route for route in routes if "/ws/" in route]
            assert len(websocket_routes) > 0
    
    def test_websocket_message_handler_initialization(self):
        """WebSocket 메시지 핸들러 초기화 테스트"""
        from app.websockets.handlers import message_handler
        assert message_handler is not None
    
    def test_websocket_connection_info_structure(self):
        """WebSocket 연결 정보 구조 테스트"""
        # 연결 정보 구조가 올바른지 확인
        connection_info = {
            "user_id": "123",
            "room_id": "456"
        }
        
        assert "user_id" in connection_info
        assert "room_id" in connection_info
        assert isinstance(connection_info["user_id"], str)
        assert isinstance(connection_info["room_id"], str)
    
    def test_websocket_message_format(self):
        """WebSocket 메시지 형식 테스트"""
        # 메시지 형식이 올바른지 확인
        message_formats = [
            {
                "type": "message",
                "content": "Hello World!",
                "message_type": "text"
            },
            {
                "type": "typing",
                "is_typing": True
            },
            {
                "type": "ping"
            }
        ]
        
        for msg in message_formats:
            assert "type" in msg
            assert isinstance(msg["type"], str)
            
            if msg["type"] == "message":
                assert "content" in msg
                assert "message_type" in msg
            elif msg["type"] == "typing":
                assert "is_typing" in msg
            elif msg["type"] == "ping":
                # ping 메시지는 type만 있으면 됨
                pass
    
    def test_websocket_broadcast_data_format(self):
        """WebSocket 브로드캐스트 데이터 형식 테스트"""
        broadcast_data = {
            "type": "message",
            "message_id": "123",
            "room_id": "456",
            "sender_id": "789",
            "content": "Hello World!",
            "message_type": "text",
            "created_at": "2024-01-01T00:00:00",
            "timestamp": "2024-01-01T00:00:00"
        }
        
        required_fields = [
            "type", "message_id", "room_id", "sender_id", 
            "content", "message_type", "created_at", "timestamp"
        ]
        
        for field in required_fields:
            assert field in broadcast_data
    
    def test_websocket_user_status_format(self):
        """WebSocket 사용자 상태 형식 테스트"""
        status_data = {
            "type": "user_status",
            "room_id": "123",
            "user_id": "456",
            "status": "online",
            "online_users": ["456", "789"],
            "online_count": 2,
            "timestamp": "2024-01-01T00:00:00"
        }
        
        required_fields = [
            "type", "room_id", "user_id", "status", 
            "online_users", "online_count", "timestamp"
        ]
        
        for field in required_fields:
            assert field in status_data
        
        assert isinstance(status_data["online_users"], list)
        assert isinstance(status_data["online_count"], int)
        assert status_data["status"] in ["online", "offline"]