import pytest
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

from app.schemas.user import UserProfile


class TestProfileAPI:
    """프로필 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_my_profile(self, client: AsyncClient, auth_token_user_1: str):
        """현재 사용자 프로필 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get("/profile/me", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert data["username"] == "testuser1"

    @pytest.mark.asyncio
    async def test_get_user_profile_by_id(
        self,
        client: AsyncClient,
        auth_token_user_1: str,
        test_user_2
    ):
        """사용자 ID로 프로필 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get(f"/profile/{test_user_2.id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user_2.id
        assert data["username"] == test_user_2.username

    @pytest.mark.asyncio
    async def test_get_nonexistent_user_profile(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """존재하지 않는 사용자 프로필 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get("/profile/99999", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_my_profile(self, client: AsyncClient, auth_token_user_1: str):
        """프로필 정보 수정 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        update_data = {
            "display_name": "Updated Display Name",
            "status_message": "새로운 상태 메시지"
        }

        response = await client.put("/profile/me", json=update_data, headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["display_name"] == update_data["display_name"]
        assert data["status_message"] == update_data["status_message"]

    @pytest.mark.asyncio
    async def test_update_profile_partial(self, client: AsyncClient, auth_token_user_1: str):
        """부분 프로필 정보 수정 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        update_data = {
            "status_message": "새로운 상태 메시지만 변경"
        }

        response = await client.put("/profile/me", json=update_data, headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status_message"] == update_data["status_message"]

    @pytest.mark.asyncio
    async def test_update_online_status(self, client: AsyncClient, auth_token_user_1: str):
        """온라인 상태 업데이트 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        status_data = {"is_online": True}

        response = await client.put("/profile/status", json=status_data, headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_online"] == True

    @pytest.mark.asyncio
    async def test_update_last_seen(self, client: AsyncClient, auth_token_user_1: str):
        """마지막 접속 시간 업데이트 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.post("/profile/last-seen", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Last seen updated successfully"

    @pytest.mark.asyncio
    async def test_search_users(self, client: AsyncClient, auth_token_user_1: str):
        """사용자 검색 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get(
            "/profile/search/users?query=testuser&limit=5",
            headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "users" in data
        assert "total_count" in data
        assert isinstance(data["users"], list)

    @pytest.mark.asyncio
    async def test_search_users_with_short_query(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """짧은 검색어로 사용자 검색 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get(
            "/profile/search/users?query=t",
            headers=headers
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: AsyncClient):
        """인증되지 않은 접근 테스트"""
        response = await client.get("/profile/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestFileUpload:
    """파일 업로드 테스트"""

    @pytest.mark.asyncio
    async def test_upload_profile_image_success(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """프로필 이미지 업로드 성공 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        # 가짜 이미지 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(b"fake image content")
            tmp_file_path = tmp_file.name

        try:
            with open(tmp_file_path, "rb") as f:
                files = {"file": ("test_image.jpg", f, "image/jpeg")}

                with patch('app.services.file_service.save_profile_image') as mock_save:
                    mock_save.return_value = "/uploads/profile_images/test_image.jpg"

                    response = await client.post(
                        "/profile/upload-image",
                        files=files,
                        headers=headers
                    )
        finally:
            Path(tmp_file_path).unlink(missing_ok=True)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "profile_image_url" in data

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """잘못된 파일 타입 업로드 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        # 텍스트 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
            tmp_file.write(b"text content")
            tmp_file_path = tmp_file.name

        try:
            with open(tmp_file_path, "rb") as f:
                files = {"file": ("test_file.txt", f, "text/plain")}

                response = await client.post(
                    "/profile/upload-image",
                    files=files,
                    headers=headers
                )
        finally:
            Path(tmp_file_path).unlink(missing_ok=True)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_delete_profile_image(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """프로필 이미지 삭제 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        # 먼저 프로필 이미지가 있는 상태로 만들기 (실제로는 모킹)
        with patch('app.services.auth_service.find_user_by_id') as mock_find_user:
            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.profile_image_url = "/uploads/profile_images/test.jpg"
            mock_find_user.return_value = mock_user

            with patch('app.services.file_service.delete_profile_image') as mock_delete:
                mock_delete.return_value = True

                response = await client.delete("/profile/image", headers=headers)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile_image(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """존재하지 않는 프로필 이미지 삭제 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.delete("/profile/image", headers=headers)

        # profile_image_url이 None인 경우 400 에러
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUserSearchAPI:
    """사용자 검색 API 테스트"""

    @pytest.mark.asyncio
    async def test_search_users_by_username(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """사용자명으로 검색 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get(
            "/users/search?query=testuser&limit=10",
            headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "users" in data
        assert "total_count" in data

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self,
        client: AsyncClient,
        auth_token_user_1: str,
        test_user_2
    ):
        """사용자 ID로 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get(f"/users/{test_user_2.id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user_2.id

    @pytest.mark.asyncio
    async def test_get_users_by_ids(
        self,
        client: AsyncClient,
        auth_token_user_1: str,
        test_user_2,
        test_user_3
    ):
        """사용자 ID 목록으로 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        user_ids = f"{test_user_2.id},{test_user_3.id}"
        response = await client.get(f"/users?user_ids={user_ids}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_users_with_invalid_ids(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """잘못된 사용자 ID 목록으로 조회 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        response = await client.get("/users?user_ids=invalid,abc", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestProfileValidation:
    """프로필 검증 테스트"""

    @pytest.mark.asyncio
    async def test_update_profile_with_too_long_status_message(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """너무 긴 상태 메시지로 프로필 수정 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        update_data = {
            "status_message": "x" * 501  # 500자 초과
        }

        response = await client.put("/profile/me", json=update_data, headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_search_with_too_long_query(
        self,
        client: AsyncClient,
        auth_token_user_1: str
    ):
        """너무 긴 검색어로 검색 테스트"""
        headers = {"Authorization": f"Bearer {auth_token_user_1}"}

        long_query = "x" * 51  # 50자 초과
        response = await client.get(
            f"/users/search?query={long_query}",
            headers=headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY