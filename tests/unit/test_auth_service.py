import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.services import auth_service
from app.models.users import User


class TestAuthServiceProfileOperations:
    """Auth 서비스의 프로필 관련 기능 테스트"""

    @pytest.mark.asyncio
    async def test_update_user_profile(self, test_session, test_user_1):
        """사용자 프로필 업데이트 테스트"""
        # 새로운 프로필 정보
        new_display_name = "새로운 표시명"
        new_status_message = "새로운 상태 메시지"

        # 프로필 업데이트
        updated_user = await auth_service.update_user_profile(
            db=test_session,
            user_id=test_user_1.id,
            display_name=new_display_name,
            status_message=new_status_message
        )

        assert updated_user is not None
        assert updated_user.display_name == new_display_name
        assert updated_user.status_message == new_status_message
        assert updated_user.updated_at > test_user_1.updated_at

    @pytest.mark.asyncio
    async def test_update_user_profile_partial(self, test_session, test_user_1):
        """사용자 프로필 부분 업데이트 테스트"""
        # 상태 메시지만 업데이트
        new_status_message = "새로운 상태 메시지만"

        updated_user = await auth_service.update_user_profile(
            db=test_session,
            user_id=test_user_1.id,
            status_message=new_status_message
        )

        assert updated_user is not None
        assert updated_user.status_message == new_status_message
        # display_name은 변경되지 않아야 함
        assert updated_user.display_name == test_user_1.display_name

    @pytest.mark.asyncio
    async def test_update_profile_nonexistent_user(self, test_session):
        """존재하지 않는 사용자 프로필 업데이트 테스트"""
        updated_user = await auth_service.update_user_profile(
            db=test_session,
            user_id=99999,
            display_name="테스트"
        )

        assert updated_user is None

    @pytest.mark.asyncio
    async def test_update_profile_image(self, test_session, test_user_1):
        """프로필 이미지 URL 업데이트 테스트"""
        new_image_url = "/uploads/profile_images/new_image.jpg"

        updated_user = await auth_service.update_profile_image(
            db=test_session,
            user_id=test_user_1.id,
            profile_image_url=new_image_url
        )

        assert updated_user is not None
        assert updated_user.profile_image_url == new_image_url
        assert updated_user.updated_at > test_user_1.updated_at

    @pytest.mark.asyncio
    async def test_update_online_status_online(self, test_session, test_user_1):
        """온라인 상태 업데이트 테스트 (온라인)"""
        updated_user = await auth_service.update_online_status(
            db=test_session,
            user_id=test_user_1.id,
            is_online=True
        )

        assert updated_user is not None
        assert updated_user.is_online == True
        # 온라인으로 변경할 때는 last_seen_at이 업데이트되지 않아야 함
        assert updated_user.last_seen_at == test_user_1.last_seen_at

    @pytest.mark.asyncio
    async def test_update_online_status_offline(self, test_session, test_user_1):
        """온라인 상태 업데이트 테스트 (오프라인)"""
        updated_user = await auth_service.update_online_status(
            db=test_session,
            user_id=test_user_1.id,
            is_online=False
        )

        assert updated_user is not None
        assert updated_user.is_online == False
        # 오프라인으로 변경할 때는 last_seen_at이 업데이트되어야 함
        assert updated_user.last_seen_at is not None

    @pytest.mark.asyncio
    async def test_update_last_seen(self, test_session, test_user_1):
        """마지막 접속 시간 업데이트 테스트"""
        original_last_seen = test_user_1.last_seen_at

        updated_user = await auth_service.update_last_seen(
            db=test_session,
            user_id=test_user_1.id
        )

        assert updated_user is not None
        assert updated_user.last_seen_at is not None
        if original_last_seen:
            assert updated_user.last_seen_at > original_last_seen

    @pytest.mark.asyncio
    async def test_search_users_by_username(self, test_session, test_user_1, test_user_2, test_user_3):
        """사용자명으로 사용자 검색 테스트"""
        # "testuser"로 검색
        users = await auth_service.search_users_by_username(
            db=test_session,
            query="testuser",
            limit=10
        )

        # test_user_1은 제외되지 않으므로 모든 사용자가 검색되어야 함
        assert len(users) >= 2  # test_user_2, test_user_3 최소 포함

        # 사용자명에 "testuser"가 포함된 사용자들인지 확인
        for user in users:
            assert "testuser" in user.username.lower()

    @pytest.mark.asyncio
    async def test_search_users_exclude_current_user(self, test_session, test_user_1, test_user_2):
        """현재 사용자 제외하고 검색 테스트"""
        users = await auth_service.search_users_by_username(
            db=test_session,
            query="testuser",
            limit=10,
            exclude_user_id=test_user_1.id
        )

        # test_user_1은 제외되어야 함
        user_ids = [user.id for user in users]
        assert test_user_1.id not in user_ids

    @pytest.mark.asyncio
    async def test_search_users_by_display_name(self, test_session, test_user_1):
        """표시명으로 사용자 검색 테스트"""
        # 사용자의 display_name 설정
        await auth_service.update_user_profile(
            db=test_session,
            user_id=test_user_1.id,
            display_name="특별한 표시명"
        )

        # display_name으로 검색
        users = await auth_service.search_users_by_username(
            db=test_session,
            query="특별한",
            limit=10
        )

        assert len(users) >= 1
        found_user = next((user for user in users if user.id == test_user_1.id), None)
        assert found_user is not None
        assert "특별한" in found_user.display_name

    @pytest.mark.asyncio
    async def test_get_user_count_by_query(self, test_session, test_user_1, test_user_2):
        """검색 쿼리에 해당하는 사용자 수 조회 테스트"""
        count = await auth_service.get_user_count_by_query(
            db=test_session,
            query="testuser"
        )

        assert count >= 2  # 최소 test_user_1, test_user_2

    @pytest.mark.asyncio
    async def test_get_user_count_exclude_current_user(self, test_session, test_user_1, test_user_2):
        """현재 사용자 제외하고 사용자 수 조회 테스트"""
        count_all = await auth_service.get_user_count_by_query(
            db=test_session,
            query="testuser"
        )

        count_excluding = await auth_service.get_user_count_by_query(
            db=test_session,
            query="testuser",
            exclude_user_id=test_user_1.id
        )

        assert count_excluding == count_all - 1

    @pytest.mark.asyncio
    async def test_get_users_by_ids(self, test_session, test_user_1, test_user_2, test_user_3):
        """사용자 ID 목록으로 사용자들 조회 테스트"""
        user_ids = [test_user_1.id, test_user_2.id, test_user_3.id]

        users = await auth_service.get_users_by_ids(
            db=test_session,
            user_ids=user_ids
        )

        assert len(users) == 3
        found_ids = [user.id for user in users]
        for user_id in user_ids:
            assert user_id in found_ids

    @pytest.mark.asyncio
    async def test_get_users_by_empty_ids(self, test_session):
        """빈 사용자 ID 목록으로 조회 테스트"""
        users = await auth_service.get_users_by_ids(
            db=test_session,
            user_ids=[]
        )

        assert users == []

    @pytest.mark.asyncio
    async def test_get_users_by_nonexistent_ids(self, test_session):
        """존재하지 않는 사용자 ID 목록으로 조회 테스트"""
        users = await auth_service.get_users_by_ids(
            db=test_session,
            user_ids=[99999, 99998]
        )

        assert users == []

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, test_session, test_user_1):
        """대소문자 구분 없는 검색 테스트"""
        # 소문자로 검색
        users_lower = await auth_service.search_users_by_username(
            db=test_session,
            query="testuser",
            limit=10
        )

        # 대문자로 검색
        users_upper = await auth_service.search_users_by_username(
            db=test_session,
            query="TESTUSER",
            limit=10
        )

        # 결과가 같아야 함 (대소문자 구분 없음)
        assert len(users_lower) == len(users_upper)

    @pytest.mark.asyncio
    async def test_search_limit_enforcement(self, test_session, test_user_1, test_user_2, test_user_3):
        """검색 결과 개수 제한 테스트"""
        users = await auth_service.search_users_by_username(
            db=test_session,
            query="testuser",
            limit=1
        )

        assert len(users) <= 1

    @pytest.mark.asyncio
    async def test_search_partial_match(self, test_session, test_user_1):
        """부분 일치 검색 테스트"""
        users = await auth_service.search_users_by_username(
            db=test_session,
            query="test",  # "testuser1"의 부분 문자열
            limit=10
        )

        # test_user_1이 검색결과에 포함되어야 함
        found_user = next((user for user in users if user.id == test_user_1.id), None)
        assert found_user is not None