import pytest
from httpx import AsyncClient
from fastapi import status


class TestMessageAPI:
    """메시지 API 테스트"""
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, client: AsyncClient, auth_token_user_1, test_chat_room, mock_message_service):
        """메시지 전송 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        message_data = {
            "content": "Hello, this is a test message!",
            "message_type": "text"
        }
        
        response = await client.post(
            f"/messages/{test_chat_room.id}", 
            json=message_data, 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["content"] == message_data["content"]
        assert data["message_type"] == message_data["message_type"]
        assert data["room_id"] == test_chat_room.id
        assert "id" in data
        assert "created_at" in data
    
    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_room(self, client: AsyncClient, auth_token_user_1, mock_message_service):
        """존재하지 않는 채팅방에 메시지 전송 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        message_data = {
            "content": "Hello, this is a test message!",
            "message_type": "text"
        }
        
        response = await client.post("/messages/99999", json=message_data, headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_send_message_to_unauthorized_room(self, client: AsyncClient, auth_token_user_3, test_chat_room, mock_message_service):
        """권한 없는 채팅방에 메시지 전송 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        message_data = {
            "content": "Hello, this is a test message!",
            "message_type": "text"
        }
        
        response = await client.post(
            f"/messages/{test_chat_room.id}", 
            json=message_data, 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access denied" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_send_empty_message(self, client: AsyncClient, auth_token_user_1, test_chat_room, mock_message_service):
        """빈 메시지 전송 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        message_data = {
            "content": "",
            "message_type": "text"
        }
        
        response = await client.post(
            f"/messages/{test_chat_room.id}", 
            json=message_data, 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_get_messages_success(self, client: AsyncClient, auth_token_user_1, test_chat_room, mock_message_service):
        """메시지 목록 조회 API 성공 테스트"""
        # 먼저 메시지를 몇 개 전송
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        for i in range(3):
            message_data = {
                "content": f"Test message {i+1}",
                "message_type": "text"
            }
            await client.post(
                f"/messages/{test_chat_room.id}", 
                json=message_data, 
                headers=headers
            )
        
        # 메시지 목록 조회
        response = await client.get(f"/messages/{test_chat_room.id}", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "messages" in data
        assert "total_count" in data
        assert len(data["messages"]) == 3
        
        # 메시지 순서 확인
        messages = data["messages"]
        assert messages[0]["content"] == "Test message 1"
        assert messages[2]["content"] == "Test message 3"
    
    @pytest.mark.asyncio
    async def test_get_messages_with_pagination(self, client: AsyncClient, auth_token_user_1, test_chat_room, mock_message_service):
        """메시지 목록 페이지네이션 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        # 페이지네이션 파라미터로 조회
        response = await client.get(
            f"/messages/{test_chat_room.id}?page=1&limit=2", 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["messages"]) <= 2
    
    @pytest.mark.asyncio
    async def test_get_messages_from_unauthorized_room(self, client: AsyncClient, auth_token_user_3, test_chat_room, mock_message_service):
        """권한 없는 채팅방의 메시지 조회 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        
        response = await client.get(f"/messages/{test_chat_room.id}", headers=headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access denied" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_get_messages_from_nonexistent_room(self, client: AsyncClient, auth_token_user_1, mock_message_service):
        """존재하지 않는 채팅방의 메시지 조회 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get("/messages/99999", headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_message_api_without_auth(self, client: AsyncClient, test_chat_room, mock_message_service):
        """인증 없이 메시지 API 접근 실패 테스트"""
        # 메시지 전송
        message_data = {"content": "Test message", "message_type": "text"}
        response = await client.post(f"/messages/{test_chat_room.id}", json=message_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 메시지 조회
        response = await client.get(f"/messages/{test_chat_room.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_send_different_message_types(self, client: AsyncClient, auth_token_user_1, test_chat_room, mock_message_service):
        """다양한 메시지 타입 전송 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        message_types = ["text", "image", "file", "emoji"]
        
        for msg_type in message_types:
            message_data = {
                "content": f"This is a {msg_type} message",
                "message_type": msg_type
            }
            
            response = await client.post(
                f"/messages/{test_chat_room.id}", 
                json=message_data, 
                headers=headers
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["message_type"] == msg_type