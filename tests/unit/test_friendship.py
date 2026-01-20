import pytest
from httpx import AsyncClient
from fastapi import status

from app.services.friendship_service import FriendshipService


class TestFriendshipService:
    """친구 관계 서비스 테스트"""
    
    @pytest.mark.asyncio
    async def test_send_friend_request_success(self, test_session, test_user_1, test_user_2):
        """친구 요청 전송 성공 테스트"""
        friendship = await FriendshipService.send_friend_request(
            test_session, test_user_1.id, test_user_2.id
        )
        
        assert friendship.user_id_1 == test_user_1.id
        assert friendship.user_id_2 == test_user_2.id
        assert friendship.status == "pending"
    
    @pytest.mark.asyncio
    async def test_send_friend_request_duplicate(self, test_session, pending_friendship):
        """중복 친구 요청 실패 테스트"""
        with pytest.raises(ValueError, match="already exists"):
            await FriendshipService.send_friend_request(
                test_session, pending_friendship.user_id_1, pending_friendship.user_id_2
            )
    
    @pytest.mark.asyncio
    async def test_find_friendship_success(self, test_session, accepted_friendship):
        """친구 관계 찾기 성공 테스트"""
        # 정방향 검색
        friendship = await FriendshipService.find_friendship(
            test_session, accepted_friendship.user_id_1, accepted_friendship.user_id_2
        )
        assert friendship is not None
        assert friendship.id == accepted_friendship.id
        
        # 역방향 검색
        friendship = await FriendshipService.find_friendship(
            test_session, accepted_friendship.user_id_2, accepted_friendship.user_id_1
        )
        assert friendship is not None
        assert friendship.id == accepted_friendship.id
    
    @pytest.mark.asyncio
    async def test_find_friendship_not_found(self, test_session, test_user_1, test_user_3):
        """존재하지 않는 친구 관계 찾기 테스트"""
        friendship = await FriendshipService.find_friendship(
            test_session, test_user_1.id, test_user_3.id
        )
        assert friendship is None
    
    @pytest.mark.asyncio
    async def test_accept_friend_request_success(self, test_session, pending_friendship):
        """친구 요청 수락 성공 테스트"""
        friendship = await FriendshipService.accept_friend_request(
            test_session, pending_friendship.id, pending_friendship.user_id_2
        )
        
        assert friendship.status == "accepted"
    
    @pytest.mark.asyncio
    async def test_accept_friend_request_wrong_user(self, test_session, pending_friendship):
        """잘못된 사용자의 친구 요청 수락 실패 테스트"""
        with pytest.raises(ValueError, match="Only the target user"):
            await FriendshipService.accept_friend_request(
                test_session, pending_friendship.id, pending_friendship.user_id_1
            )
    
    @pytest.mark.asyncio
    async def test_reject_friend_request_success(self, test_session, pending_friendship):
        """친구 요청 거절 성공 테스트"""
        result = await FriendshipService.reject_friend_request(
            test_session, pending_friendship.id, pending_friendship.user_id_2
        )
        
        assert result is True
        
        # 거절된 요청은 soft delete되어야 함
        await test_session.refresh(pending_friendship)
        assert pending_friendship.deleted_at is not None
    
    @pytest.mark.asyncio
    async def test_get_friends_list(self, test_session, accepted_friendship, test_user_1):
        """친구 목록 조회 테스트"""
        friends = await FriendshipService.get_friends_list(test_session, test_user_1.id)
        
        assert len(friends) == 1
        friend_user, friendship_date = friends[0]
        assert friend_user.id == accepted_friendship.user_id_2
        assert friendship_date == accepted_friendship.created_at
    
    @pytest.mark.asyncio
    async def test_get_friend_requests(self, test_session, pending_friendship, test_user_1, test_user_3):
        """친구 요청 목록 조회 테스트"""
        # 받은 요청과 보낸 요청 조회
        received_requests, sent_requests = await FriendshipService.get_friend_requests(
            test_session, test_user_3.id
        )
        
        assert len(received_requests) == 1
        assert len(sent_requests) == 0
        
        friendship, requester = received_requests[0]
        assert friendship.id == pending_friendship.id
        assert requester.id == test_user_1.id
    
    @pytest.mark.asyncio
    async def test_are_friends_true(self, test_session, accepted_friendship):
        """친구 여부 확인 - 친구인 경우"""
        are_friends = await FriendshipService.are_friends(
            test_session, accepted_friendship.user_id_1, accepted_friendship.user_id_2
        )
        assert are_friends is True
    
    @pytest.mark.asyncio
    async def test_are_friends_false(self, test_session, test_user_1, test_user_3):
        """친구 여부 확인 - 친구가 아닌 경우"""
        are_friends = await FriendshipService.are_friends(
            test_session, test_user_1.id, test_user_3.id
        )
        assert are_friends is False


class TestFriendshipAPI:
    """친구 관계 API 테스트"""
    
    @pytest.mark.asyncio
    async def test_send_friend_request_success(self, client: AsyncClient, auth_token_user_1, test_user_2):
        """친구 요청 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        request_data = {"user_id_2": test_user_2.id}
        
        response = await client.post("/friends/request", json=request_data, headers=headers)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "pending"
        assert data["user_id_2"] == test_user_2.id
    
    @pytest.mark.asyncio
    async def test_send_friend_request_to_self(self, client: AsyncClient, auth_token_user_1, test_user_1):
        """자기 자신에게 친구 요청 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        request_data = {"user_id_2": test_user_1.id}
        
        response = await client.post("/friends/request", json=request_data, headers=headers)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_send_friend_request_to_nonexistent_user(self, client: AsyncClient, auth_token_user_1):
        """존재하지 않는 사용자에게 친구 요청 실패 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        request_data = {"user_id_2": 99999}
        
        response = await client.post("/friends/request", json=request_data, headers=headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_accept_friend_request_success(self, client: AsyncClient, pending_friendship, auth_token_user_3):
        """친구 요청 수락 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        status_data = {"action": "accept"}
        
        response = await client.put(
            f"/friends/{pending_friendship.id}/status", 
            json=status_data, 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "accepted"
    
    @pytest.mark.asyncio
    async def test_reject_friend_request_success(self, client: AsyncClient, pending_friendship, auth_token_user_3):
        """친구 요청 거절 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        status_data = {"action": "reject"}
        
        response = await client.put(
            f"/friends/{pending_friendship.id}/status", 
            json=status_data, 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert "rejected successfully" in response.json()["message"]
    
    @pytest.mark.asyncio
    async def test_get_friends_list_success(self, client: AsyncClient, accepted_friendship, auth_token_user_1):
        """친구 목록 조회 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}
        
        response = await client.get("/friends", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "user_id" in data[0]
        assert "username" in data[0]
        assert "email" in data[0]
    
    @pytest.mark.asyncio
    async def test_get_friend_requests_success(self, client: AsyncClient, pending_friendship, auth_token_user_3):
        """친구 요청 목록 조회 API 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_3}"}
        
        response = await client.get("/friends/requests", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "received_requests" in data
        assert "sent_requests" in data
        assert len(data["received_requests"]) == 1
        assert len(data["sent_requests"]) == 0
    
    @pytest.mark.asyncio
    async def test_friend_api_without_auth(self, client: AsyncClient):
        """인증 없이 친구 API 접근 실패 테스트"""
        # 친구 요청 전송
        response = await client.post("/friends/request", json={"user_id_2": 1})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 친구 목록 조회
        response = await client.get("/friends")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 친구 요청 목록 조회
        response = await client.get("/friends/requests")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED