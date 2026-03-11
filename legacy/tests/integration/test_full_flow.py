import pytest
from httpx import AsyncClient
from fastapi import status


class TestFullChatFlow:
    """전체 채팅 플로우 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_complete_chat_flow(self, client: AsyncClient):
        """
        완전한 채팅 플로우 테스트:
        1. 사용자 A, B 회원가입
        2. A가 B에게 친구 요청
        3. B가 친구 요청 수락
        4. A가 B와 채팅방 생성
        5. A, B가 메시지 주고받기
        6. WebSocket 상태 확인
        """
        
        # 1. 사용자 A, B 회원가입
        user_a_data = {
            "username": "alice",
            "email": "alice@example.com",
            "password": "alicepass123!"
        }
        
        user_b_data = {
            "username": "bob",
            "email": "bob@example.com",
            "password": "bobpass123!"
        }
        
        # 사용자 A 회원가입
        response_a = await client.post("/auth/register", json=user_a_data)
        assert response_a.status_code == status.HTTP_201_CREATED
        user_a = response_a.json()
        
        # 사용자 B 회원가입
        response_b = await client.post("/auth/register", json=user_b_data)
        assert response_b.status_code == status.HTTP_201_CREATED
        user_b = response_b.json()
        
        # 로그인하여 토큰 획득
        login_a = await client.post("/auth/login", json={
            "email": user_a_data["email"],
            "password": user_a_data["password"]
        })
        assert login_a.status_code == status.HTTP_200_OK
        token_a = login_a.json()["access_token"]
        
        login_b = await client.post("/auth/login", json={
            "email": user_b_data["email"],
            "password": user_b_data["password"]
        })
        assert login_b.status_code == status.HTTP_200_OK
        token_b = login_b.json()["access_token"]
        
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}
        
        # 2. A가 B에게 친구 요청
        friend_request = await client.post(
            "/friends/request",
            json={"user_id_2": user_b["id"]},
            headers=headers_a
        )
        assert friend_request.status_code == status.HTTP_201_CREATED
        friendship = friend_request.json()
        assert friendship["status"] == "pending"
        
        # B의 친구 요청 목록 확인
        requests_b = await client.get("/friends/requests", headers=headers_b)
        assert requests_b.status_code == status.HTTP_200_OK
        requests_data = requests_b.json()
        assert len(requests_data["received_requests"]) == 1
        assert requests_data["received_requests"][0]["username"] == user_a["username"]
        
        # 3. B가 친구 요청 수락
        accept_request = await client.put(
            f"/friends/{friendship['id']}/status",
            json={"action": "accept"},
            headers=headers_b
        )
        assert accept_request.status_code == status.HTTP_200_OK
        accepted_friendship = accept_request.json()
        assert accepted_friendship["status"] == "accepted"
        
        # 친구 목록 확인
        friends_a = await client.get("/friends", headers=headers_a)
        assert friends_a.status_code == status.HTTP_200_OK
        assert len(friends_a.json()) == 1
        assert friends_a.json()[0]["username"] == user_b["username"]
        
        friends_b = await client.get("/friends", headers=headers_b)
        assert friends_b.status_code == status.HTTP_200_OK
        assert len(friends_b.json()) == 1
        assert friends_b.json()[0]["username"] == user_a["username"]
        
        # 4. A가 B와 채팅방 생성
        create_room = await client.post(
            "/chat-rooms",
            json={"participant_id": user_b["id"]},
            headers=headers_a
        )
        assert create_room.status_code == status.HTTP_201_CREATED
        chat_room = create_room.json()
        room_id = chat_room["id"]
        
        # 채팅방 목록 확인
        rooms_a = await client.get("/chat-rooms", headers=headers_a)
        assert rooms_a.status_code == status.HTTP_200_OK
        assert len(rooms_a.json()) == 1
        
        rooms_b = await client.get("/chat-rooms", headers=headers_b)
        assert rooms_b.status_code == status.HTTP_200_OK
        assert len(rooms_b.json()) == 1
        
        # 5. A, B가 메시지 주고받기
        # A가 첫 번째 메시지 전송
        message_1 = await client.post(
            f"/messages/{room_id}",
            json={"content": "Hello Bob! How are you?", "message_type": "text"},
            headers=headers_a
        )
        assert message_1.status_code == status.HTTP_201_CREATED
        msg_1_data = message_1.json()
        assert msg_1_data["content"] == "Hello Bob! How are you?"
        
        # B가 응답 메시지 전송
        message_2 = await client.post(
            f"/messages/{room_id}",
            json={"content": "Hi Alice! I'm doing great, thanks!", "message_type": "text"},
            headers=headers_b
        )
        assert message_2.status_code == status.HTTP_201_CREATED
        msg_2_data = message_2.json()
        assert msg_2_data["content"] == "Hi Alice! I'm doing great, thanks!"
        
        # A가 또 다른 메시지 전송
        message_3 = await client.post(
            f"/messages/{room_id}",
            json={"content": "That's wonderful to hear! 😊", "message_type": "text"},
            headers=headers_a
        )
        assert message_3.status_code == status.HTTP_201_CREATED
        
        # 메시지 목록 조회 (A 관점)
        messages_a = await client.get(f"/messages/{room_id}", headers=headers_a)
        assert messages_a.status_code == status.HTTP_200_OK
        messages_data_a = messages_a.json()
        assert messages_data_a["total_count"] == 3
        assert len(messages_data_a["messages"]) == 3
        
        # 메시지 순서 확인 (최신순)
        messages = messages_data_a["messages"]
        assert messages[0]["content"] == "That's wonderful to hear! 😊"
        assert messages[1]["content"] == "Hi Alice! I'm doing great, thanks!"
        assert messages[2]["content"] == "Hello Bob! How are you?"
        
        # 메시지 목록 조회 (B 관점)
        messages_b = await client.get(f"/messages/{room_id}", headers=headers_b)
        assert messages_b.status_code == status.HTTP_200_OK
        messages_data_b = messages_b.json()
        assert messages_data_b["total_count"] == 3
        
        # 6. WebSocket 상태 확인
        # A의 WebSocket 상태 확인
        ws_status_a = await client.get(f"/ws/rooms/{room_id}/status", headers=headers_a)
        assert ws_status_a.status_code == status.HTTP_200_OK
        status_data_a = ws_status_a.json()
        assert status_data_a["room_id"] == str(room_id)
        assert status_data_a["online_count"] == 0  # 실제로 연결된 WebSocket이 없으므로 0
        
        # B의 WebSocket 상태 확인
        ws_status_b = await client.get(f"/ws/rooms/{room_id}/status", headers=headers_b)
        assert ws_status_b.status_code == status.HTTP_200_OK
        status_data_b = ws_status_b.json()
        assert status_data_b["room_id"] == str(room_id)
        
        # 최종 검증: 전체 플로우가 성공적으로 완료됨
        assert user_a["id"] != user_b["id"]  # 서로 다른 사용자
        assert accepted_friendship["status"] == "accepted"  # 친구 관계 수락
        assert chat_room["room_type"] == "direct"  # 1:1 채팅방
        assert messages_data_a["total_count"] == 3  # 3개의 메시지 교환
    
    @pytest.mark.asyncio
    async def test_friend_request_rejection_flow(self, client: AsyncClient):
        """
        친구 요청 거절 플로우 테스트:
        1. 사용자 C, D 회원가입
        2. C가 D에게 친구 요청
        3. D가 친구 요청 거절
        4. C가 D와 채팅방 생성 시도 (성공해야 함 - 친구가 아니어도 채팅 가능)
        """
        
        # 1. 사용자 C, D 회원가입
        user_c_data = {
            "username": "charlie",
            "email": "charlie@example.com",
            "password": "charliepass123!"
        }
        
        user_d_data = {
            "username": "diana",
            "email": "diana@example.com",
            "password": "dianapass123!"
        }
        
        # 사용자 C 회원가입 및 로그인
        response_c = await client.post("/auth/register", json=user_c_data)
        assert response_c.status_code == status.HTTP_201_CREATED
        user_c = response_c.json()
        
        login_c = await client.post("/auth/login", json={
            "email": user_c_data["email"],
            "password": user_c_data["password"]
        })
        token_c = login_c.json()["access_token"]
        headers_c = {"Authorization": f"Bearer {token_c}"}
        
        # 사용자 D 회원가입 및 로그인
        response_d = await client.post("/auth/register", json=user_d_data)
        assert response_d.status_code == status.HTTP_201_CREATED
        user_d = response_d.json()
        
        login_d = await client.post("/auth/login", json={
            "email": user_d_data["email"],
            "password": user_d_data["password"]
        })
        token_d = login_d.json()["access_token"]
        headers_d = {"Authorization": f"Bearer {token_d}"}
        
        # 2. C가 D에게 친구 요청
        friend_request = await client.post(
            "/friends/request",
            json={"user_id_2": user_d["id"]},
            headers=headers_c
        )
        assert friend_request.status_code == status.HTTP_201_CREATED
        friendship = friend_request.json()
        
        # 3. D가 친구 요청 거절
        reject_request = await client.put(
            f"/friends/{friendship['id']}/status",
            json={"action": "reject"},
            headers=headers_d
        )
        assert reject_request.status_code == status.HTTP_200_OK
        assert "rejected successfully" in reject_request.json()["message"]
        
        # 친구 목록이 비어있는지 확인
        friends_c = await client.get("/friends", headers=headers_c)
        assert friends_c.status_code == status.HTTP_200_OK
        assert len(friends_c.json()) == 0
        
        friends_d = await client.get("/friends", headers=headers_d)
        assert friends_d.status_code == status.HTTP_200_OK
        assert len(friends_d.json()) == 0
        
        # 4. C가 D와 채팅방 생성 시도 (친구가 아니어도 가능)
        create_room = await client.post(
            "/chat-rooms",
            json={"participant_id": user_d["id"]},
            headers=headers_c
        )
        assert create_room.status_code == status.HTTP_201_CREATED
        chat_room = create_room.json()
        
        # 채팅방이 성공적으로 생성되었는지 확인
        assert chat_room["room_type"] == "direct"
        assert "id" in chat_room
    
    @pytest.mark.asyncio
    async def test_multiple_users_chat_scenario(self, client: AsyncClient):
        """
        다중 사용자 채팅 시나리오 테스트:
        1. 사용자 E, F, G 회원가입
        2. E-F, E-G 친구 관계 성립
        3. E가 F, G와 각각 채팅방 생성
        4. 각 채팅방에서 메시지 교환
        5. E의 채팅방 목록 확인
        """
        
        # 1. 사용자 E, F, G 회원가입
        users_data = [
            {"username": "eve", "email": "eve@example.com", "password": "evepass123!"},
            {"username": "frank", "email": "frank@example.com", "password": "frankpass123!"},
            {"username": "grace", "email": "grace@example.com", "password": "gracepass123!"}
        ]
        
        users = []
        tokens = []
        headers = []
        
        for user_data in users_data:
            # 회원가입
            response = await client.post("/auth/register", json=user_data)
            assert response.status_code == status.HTTP_201_CREATED
            users.append(response.json())
            
            # 로그인
            login = await client.post("/auth/login", json={
                "email": user_data["email"],
                "password": user_data["password"]
            })
            token = login.json()["access_token"]
            tokens.append(token)
            headers.append({"Authorization": f"Bearer {token}"})
        
        user_e, user_f, user_g = users
        headers_e, headers_f, headers_g = headers
        
        # 2. E-F, E-G 친구 관계 성립
        # E가 F에게 친구 요청
        request_ef = await client.post(
            "/friends/request",
            json={"user_id_2": user_f["id"]},
            headers=headers_e
        )
        friendship_ef = request_ef.json()
        
        # F가 수락
        await client.put(
            f"/friends/{friendship_ef['id']}/status",
            json={"action": "accept"},
            headers=headers_f
        )
        
        # E가 G에게 친구 요청
        request_eg = await client.post(
            "/friends/request",
            json={"user_id_2": user_g["id"]},
            headers=headers_e
        )
        friendship_eg = request_eg.json()
        
        # G가 수락
        await client.put(
            f"/friends/{friendship_eg['id']}/status",
            json={"action": "accept"},
            headers=headers_g
        )
        
        # E의 친구 목록 확인 (2명이어야 함)
        friends_e = await client.get("/friends", headers=headers_e)
        assert len(friends_e.json()) == 2
        
        # 3. E가 F, G와 각각 채팅방 생성
        room_ef = await client.post(
            "/chat-rooms",
            json={"participant_id": user_f["id"]},
            headers=headers_e
        )
        chat_room_ef = room_ef.json()
        
        room_eg = await client.post(
            "/chat-rooms",
            json={"participant_id": user_g["id"]},
            headers=headers_e
        )
        chat_room_eg = room_eg.json()
        
        # 4. 각 채팅방에서 메시지 교환
        # E-F 채팅방
        await client.post(
            f"/messages/{chat_room_ef['id']}",
            json={"content": "Hi Frank!", "message_type": "text"},
            headers=headers_e
        )
        
        await client.post(
            f"/messages/{chat_room_ef['id']}",
            json={"content": "Hello Eve!", "message_type": "text"},
            headers=headers_f
        )
        
        # E-G 채팅방
        await client.post(
            f"/messages/{chat_room_eg['id']}",
            json={"content": "Hi Grace!", "message_type": "text"},
            headers=headers_e
        )
        
        await client.post(
            f"/messages/{chat_room_eg['id']}",
            json={"content": "Hello Eve!", "message_type": "text"},
            headers=headers_g
        )
        
        # 5. E의 채팅방 목록 확인
        rooms_e = await client.get("/chat-rooms", headers=headers_e)
        assert rooms_e.status_code == status.HTTP_200_OK
        rooms_data = rooms_e.json()
        assert len(rooms_data) == 2
        
        # 각 채팅방의 메시지 확인
        messages_ef = await client.get(f"/messages/{chat_room_ef['id']}", headers=headers_e)
        assert messages_ef.json()["total_count"] == 2
        
        messages_eg = await client.get(f"/messages/{chat_room_eg['id']}", headers=headers_e)
        assert messages_eg.json()["total_count"] == 2


class TestProfileIntegrationFlow:
    """프로필 관련 통합 테스트"""

    @pytest.mark.asyncio
    async def test_complete_profile_management_flow(self, client: AsyncClient):
        """
        완전한 프로필 관리 플로우 테스트:
        1. 사용자 회원가입 및 로그인
        2. 프로필 정보 조회
        3. 프로필 정보 수정
        4. 온라인 상태 업데이트
        5. 사용자 검색
        6. 마지막 접속 시간 업데이트
        """

        # 1. 사용자 회원가입 및 로그인
        user_data = {
            "username": "profileuser",
            "email": "profile@example.com",
            "password": "profilepass123!"
        }

        # 회원가입
        register_response = await client.post("/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED
        user = register_response.json()

        # 로그인
        login_response = await client.post("/auth/login", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        assert login_response.status_code == status.HTTP_200_OK
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. 프로필 정보 조회
        profile_response = await client.get("/profile/me", headers=headers)
        assert profile_response.status_code == status.HTTP_200_OK
        profile_data = profile_response.json()
        assert profile_data["username"] == user_data["username"]
        assert profile_data["is_online"] == False  # 기본값
        assert profile_data["status_message"] is None  # 기본값

        # 3. 프로필 정보 수정
        update_data = {
            "display_name": "멋진 사용자",
            "status_message": "오늘 하루도 화이팅! 💪"
        }

        update_response = await client.put("/profile/me", json=update_data, headers=headers)
        assert update_response.status_code == status.HTTP_200_OK
        updated_profile = update_response.json()
        assert updated_profile["display_name"] == update_data["display_name"]
        assert updated_profile["status_message"] == update_data["status_message"]

        # 4. 온라인 상태 업데이트
        status_update = {"is_online": True}
        status_response = await client.put("/profile/status", json=status_update, headers=headers)
        assert status_response.status_code == status.HTTP_200_OK
        status_data = status_response.json()
        assert status_data["is_online"] == True

        # 5. 마지막 접속 시간 업데이트
        last_seen_response = await client.post("/profile/last-seen", headers=headers)
        assert last_seen_response.status_code == status.HTTP_200_OK
        assert last_seen_response.json()["message"] == "Last seen updated successfully"

        # 6. 사용자 검색 (다른 사용자 생성 후)
        # 검색할 다른 사용자 생성
        other_user_data = {
            "username": "searchableuser",
            "email": "searchable@example.com",
            "password": "searchpass123!"
        }
        await client.post("/auth/register", json=other_user_data)

        # 사용자 검색
        search_response = await client.get(
            "/users/search?query=searchable&limit=5",
            headers=headers
        )
        assert search_response.status_code == status.HTTP_200_OK
        search_data = search_response.json()
        assert search_data["total_count"] >= 1
        assert len(search_data["users"]) >= 1

        # 검색 결과에서 생성한 사용자 찾기
        found_user = next(
            (user for user in search_data["users"] if user["username"] == other_user_data["username"]),
            None
        )
        assert found_user is not None

    @pytest.mark.asyncio
    async def test_user_search_and_profile_viewing_flow(self, client: AsyncClient):
        """
        사용자 검색 및 프로필 조회 플로우 테스트:
        1. 두 사용자 생성
        2. 사용자 A가 사용자 B 검색
        3. 사용자 A가 사용자 B의 프로필 조회
        4. 다중 사용자 ID로 프로필 조회
        """

        # 1. 두 사용자 생성
        user_a_data = {
            "username": "searcher",
            "email": "searcher@example.com",
            "password": "searcherpass123!"
        }

        user_b_data = {
            "username": "searchable_target",
            "email": "target@example.com",
            "password": "targetpass123!"
        }

        # 사용자 A 생성 및 로그인
        register_a = await client.post("/auth/register", json=user_a_data)
        user_a = register_a.json()

        login_a = await client.post("/auth/login", json={
            "email": user_a_data["email"],
            "password": user_a_data["password"]
        })
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 사용자 B 생성 및 프로필 설정
        register_b = await client.post("/auth/register", json=user_b_data)
        user_b = register_b.json()

        login_b = await client.post("/auth/login", json={
            "email": user_b_data["email"],
            "password": user_b_data["password"]
        })
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 사용자 B 프로필 설정
        await client.put("/profile/me", json={
            "display_name": "검색 가능한 사용자",
            "status_message": "검색해보세요!"
        }, headers=headers_b)

        # 2. 사용자 A가 사용자 B 검색
        search_response = await client.get(
            "/users/search?query=searchable&limit=10",
            headers=headers_a
        )
        assert search_response.status_code == status.HTTP_200_OK
        search_data = search_response.json()

        # 사용자 B가 검색 결과에 있는지 확인
        found_user_b = next(
            (user for user in search_data["users"] if user["id"] == user_b["id"]),
            None
        )
        assert found_user_b is not None
        assert found_user_b["username"] == user_b_data["username"]

        # 3. 사용자 A가 사용자 B의 프로필 조회
        profile_response = await client.get(f"/users/{user_b['id']}", headers=headers_a)
        assert profile_response.status_code == status.HTTP_200_OK
        profile_data = profile_response.json()
        assert profile_data["id"] == user_b["id"]
        assert profile_data["display_name"] == "검색 가능한 사용자"
        assert profile_data["status_message"] == "검색해보세요!"

        # 4. 다중 사용자 ID로 프로필 조회
        # 추가 사용자 생성
        user_c_data = {
            "username": "thirduser",
            "email": "third@example.com",
            "password": "thirdpass123!"
        }
        register_c = await client.post("/auth/register", json=user_c_data)
        user_c = register_c.json()

        # 다중 사용자 조회
        user_ids = f"{user_b['id']},{user_c['id']}"
        multi_response = await client.get(f"/users?user_ids={user_ids}", headers=headers_a)
        assert multi_response.status_code == status.HTTP_200_OK
        multi_data = multi_response.json()
        assert len(multi_data) == 2

        # 조회된 사용자들이 올바른지 확인
        found_ids = [user["id"] for user in multi_data]
        assert user_b["id"] in found_ids
        assert user_c["id"] in found_ids

    @pytest.mark.asyncio
    async def test_profile_update_and_search_integration(self, client: AsyncClient):
        """
        프로필 업데이트와 검색 통합 테스트:
        1. 사용자 생성 및 초기 프로필 설정
        2. 다른 사용자가 검색 (display_name으로)
        3. 프로필 정보 변경
        4. 변경된 정보로 다시 검색
        5. 온라인 상태 변경 및 확인
        """

        # 1. 두 사용자 생성
        user_updater_data = {
            "username": "updater",
            "email": "updater@example.com",
            "password": "updaterpass123!"
        }

        user_searcher_data = {
            "username": "searcher2",
            "email": "searcher2@example.com",
            "password": "searcher2pass123!"
        }

        # 사용자 생성 및 로그인
        register_updater = await client.post("/auth/register", json=user_updater_data)
        user_updater = register_updater.json()

        login_updater = await client.post("/auth/login", json={
            "email": user_updater_data["email"],
            "password": user_updater_data["password"]
        })
        token_updater = login_updater.json()["access_token"]
        headers_updater = {"Authorization": f"Bearer {token_updater}"}

        register_searcher = await client.post("/auth/register", json=user_searcher_data)
        user_searcher = register_searcher.json()

        login_searcher = await client.post("/auth/login", json={
            "email": user_searcher_data["email"],
            "password": user_searcher_data["password"]
        })
        token_searcher = login_searcher.json()["access_token"]
        headers_searcher = {"Authorization": f"Bearer {token_searcher}"}

        # 2. 초기 프로필 설정
        initial_profile = {
            "display_name": "초기 표시명",
            "status_message": "초기 상태 메시지"
        }

        await client.put("/profile/me", json=initial_profile, headers=headers_updater)

        # 3. 다른 사용자가 display_name으로 검색
        search_initial = await client.get(
            "/users/search?query=초기&limit=10",
            headers=headers_searcher
        )
        assert search_initial.status_code == status.HTTP_200_OK
        initial_results = search_initial.json()

        # 검색 결과에 updater가 있는지 확인
        found_initial = next(
            (user for user in initial_results["users"] if user["id"] == user_updater["id"]),
            None
        )
        assert found_initial is not None
        assert "초기" in found_initial["display_name"]

        # 4. 프로필 정보 변경
        updated_profile = {
            "display_name": "변경된 표시명",
            "status_message": "새로운 상태 메시지"
        }

        update_response = await client.put("/profile/me", json=updated_profile, headers=headers_updater)
        assert update_response.status_code == status.HTTP_200_OK

        # 5. 변경된 정보로 다시 검색
        search_updated = await client.get(
            "/users/search?query=변경된&limit=10",
            headers=headers_searcher
        )
        assert search_updated.status_code == status.HTTP_200_OK
        updated_results = search_updated.json()

        # 변경된 정보로 검색 가능한지 확인
        found_updated = next(
            (user for user in updated_results["users"] if user["id"] == user_updater["id"]),
            None
        )
        assert found_updated is not None
        assert "변경된" in found_updated["display_name"]

        # 6. 온라인 상태 변경 및 확인
        # 온라인으로 변경
        await client.put("/profile/status", json={"is_online": True}, headers=headers_updater)

        # 프로필 조회로 온라인 상태 확인
        profile_check = await client.get(f"/users/{user_updater['id']}", headers=headers_searcher)
        profile_data = profile_check.json()
        assert profile_data["is_online"] == True
        assert profile_data["display_name"] == "변경된 표시명"
        assert profile_data["status_message"] == "새로운 상태 메시지"

        # 오프라인으로 변경
        await client.put("/profile/status", json={"is_online": False}, headers=headers_updater)

        # 다시 확인
        profile_check_offline = await client.get(f"/users/{user_updater['id']}", headers=headers_searcher)
        profile_data_offline = profile_check_offline.json()
        assert profile_data_offline["is_online"] == False
        assert profile_data_offline["last_seen_at"] is not None  # 오프라인으로 변경시 last_seen_at 업데이트