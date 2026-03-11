import pytest
from httpx import AsyncClient
from fastapi import status


class TestChatRoomAPI:
    """채팅방 API 테스트"""
    
    @pytest.mark.asyncio
    async def test_create_chat_room_success(self, client: AsyncClient, auth_token_user_1, test_user_2):
        """채팅방 생성 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        room_data = {"participant_id": test_user_2.id}
        
        response = await client.post("/chat-rooms", json=room_data, headers=headers)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert "room_type" in data
        assert data["room_type"] == "direct"
        assert "participants" in data
    
    @pytest.mark.asyncio
    async def test_create_chat_room_with_self(self, client: AsyncClient, auth_token_user_1, test_user_1):
        """자기 자신과 채팅방 생성 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        room_data = {"participant_id": test_user_1.id}
        
        response = await client.post("/chat-rooms", json=room_data, headers=headers)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_create_chat_room_with_nonexistent_user(self, client: AsyncClient, auth_token_user_1):
        """존재하지 않는 사용자와 채팅방 생성 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        room_data = {"participant_id": 99999}
        
        response = await client.post("/chat-rooms", json=room_data, headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_create_existing_chat_room(self, client: AsyncClient, auth_token_user_1, test_chat_room, test_user_2):
        """기존 채팅방이 있는 경우 기존 방 반환 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        room_data = {"participant_id": test_user_2.id}
        
        response = await client.post("/chat-rooms", json=room_data, headers=headers)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["id"] == test_chat_room.id
    
    @pytest.mark.asyncio
    async def test_get_chat_rooms_list(self, client: AsyncClient, auth_token_user_1, test_chat_room):
        """채팅방 목록 조회 API 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get("/chat-rooms", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # 생성한 채팅방이 목록에 있는지 확인
        room_ids = [room["id"] for room in data]
        assert test_chat_room.id in room_ids
    
    @pytest.mark.asyncio
    async def test_get_chat_room_detail(self, client: AsyncClient, auth_token_user_1, test_chat_room):
        """채팅방 상세 조회 API 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get(f"/chat-rooms/{test_chat_room.id}", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_chat_room.id
        assert "participants" in data
        assert "last_message" in data
    
    @pytest.mark.asyncio
    async def test_get_chat_room_detail_unauthorized(self, client: AsyncClient, auth_token_user_3, test_chat_room):
        """권한 없는 사용자의 채팅방 상세 조회 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        
        response = await client.get(f"/chat-rooms/{test_chat_room.id}", headers=headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access denied" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_chat_room(self, client: AsyncClient, auth_token_user_1):
        """존재하지 않는 채팅방 조회 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get("/chat-rooms/99999", headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_chat_room_api_without_auth(self, client: AsyncClient):
        """인증 없이 채팅방 API 접근 실패 테스트"""
        # 채팅방 생성
        response = await client.post("/chat-rooms", json={"participant_id": 1})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 채팅방 목록 조회
        response = await client.get("/chat-rooms")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 채팅방 상세 조회
        response = await client.get("/chat-rooms/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED