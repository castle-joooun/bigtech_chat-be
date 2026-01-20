import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException, UploadFile
import io

from app.services import file_service


class TestFileValidation:
    """파일 검증 테스트"""

    def test_get_file_extension(self):
        """파일 확장자 추출 테스트"""
        assert file_service.get_file_extension("test.jpg") == ".jpg"
        assert file_service.get_file_extension("image.PNG") == ".png"
        assert file_service.get_file_extension("file.jpeg") == ".jpeg"
        assert file_service.get_file_extension("noextension") == ""

    def test_is_allowed_image_file(self):
        """허용된 이미지 파일 검증 테스트"""
        assert file_service.is_allowed_image_file("test.jpg") == True
        assert file_service.is_allowed_image_file("image.PNG") == True
        assert file_service.is_allowed_image_file("photo.jpeg") == True
        assert file_service.is_allowed_image_file("animated.gif") == True
        assert file_service.is_allowed_image_file("modern.webp") == True

        assert file_service.is_allowed_image_file("document.pdf") == False
        assert file_service.is_allowed_image_file("text.txt") == False
        assert file_service.is_allowed_image_file("video.mp4") == False

    def test_generate_unique_filename(self):
        """고유한 파일명 생성 테스트"""
        original_filename = "test.jpg"

        filename1 = file_service.generate_unique_filename(original_filename)
        filename2 = file_service.generate_unique_filename(original_filename)

        # 파일명이 다라야 함
        assert filename1 != filename2

        # 둘 다 .jpg 확장자를 가져야 함
        assert filename1.endswith(".jpg")
        assert filename2.endswith(".jpg")

    def test_validate_file_size(self):
        """파일 크기 검증 테스트"""
        # 허용 범위 내
        assert file_service.validate_file_size(1024) == True  # 1KB
        assert file_service.validate_file_size(1024 * 1024) == True  # 1MB
        assert file_service.validate_file_size(5 * 1024 * 1024) == True  # 5MB (최대값)

        # 허용 범위 초과
        assert file_service.validate_file_size(5 * 1024 * 1024 + 1) == False  # 5MB + 1byte
        assert file_service.validate_file_size(10 * 1024 * 1024) == False  # 10MB

    def test_ensure_upload_directories(self):
        """업로드 디렉토리 생성 테스트"""
        with patch('app.services.file_service.UPLOAD_DIR') as mock_upload_dir, \
             patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:

            mock_upload_dir.mkdir = AsyncMock()
            mock_profile_dir.mkdir = AsyncMock()

            file_service.ensure_upload_directories()

            mock_upload_dir.mkdir.assert_called_once_with(exist_ok=True)
            mock_profile_dir.mkdir.assert_called_once_with(exist_ok=True)


class TestFileUpload:
    """파일 업로드 테스트"""

    @pytest.mark.asyncio
    async def test_validate_uploaded_file_success(self):
        """유효한 파일 검증 성공 테스트"""
        # 가짜 UploadFile 객체 생성
        file_content = b"fake image content"
        upload_file = UploadFile(
            filename="test.jpg",
            file=io.BytesIO(file_content),
            size=len(file_content)
        )

        # 예외가 발생하지 않아야 함
        await file_service.validate_uploaded_file(upload_file)

    @pytest.mark.asyncio
    async def test_validate_uploaded_file_no_filename(self):
        """파일명이 없는 경우 검증 테스트"""
        upload_file = UploadFile(filename=None, file=io.BytesIO(b"content"))

        with pytest.raises(HTTPException) as exc_info:
            await file_service.validate_uploaded_file(upload_file)

        assert exc_info.value.status_code == 400
        assert "No file provided" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_uploaded_file_invalid_extension(self):
        """잘못된 확장자 파일 검증 테스트"""
        upload_file = UploadFile(
            filename="document.pdf",
            file=io.BytesIO(b"pdf content")
        )

        with pytest.raises(HTTPException) as exc_info:
            await file_service.validate_uploaded_file(upload_file)

        assert exc_info.value.status_code == 400
        assert "Invalid file type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_uploaded_file_too_large(self):
        """파일 크기 초과 검증 테스트"""
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        upload_file = UploadFile(
            filename="large.jpg",
            file=io.BytesIO(large_content),
            size=len(large_content)
        )

        with pytest.raises(HTTPException) as exc_info:
            await file_service.validate_uploaded_file(upload_file)

        assert exc_info.value.status_code == 400
        assert "File size exceeds" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_save_profile_image_success(self):
        """프로필 이미지 저장 성공 테스트"""
        file_content = b"fake image content"
        upload_file = UploadFile(
            filename="test.jpg",
            file=io.BytesIO(file_content)
        )

        with patch('app.services.file_service.ensure_upload_directories'), \
             patch('aiofiles.open', create=True) as mock_aiofiles_open, \
             patch('app.services.file_service.generate_unique_filename') as mock_generate_filename:

            mock_generate_filename.return_value = "unique_test.jpg"

            # aiofiles.open을 모킹
            mock_file = AsyncMock()
            mock_aiofiles_open.return_value.__aenter__.return_value = mock_file

            result = await file_service.save_profile_image(upload_file, user_id=1)

            assert result == "/uploads/profile_images/unique_test.jpg"
            mock_file.write.assert_called_once_with(file_content)

    @pytest.mark.asyncio
    async def test_save_profile_image_content_too_large(self):
        """실제 파일 내용이 너무 큰 경우 테스트"""
        # 작은 크기로 생성하지만 읽을 때는 큰 내용
        upload_file = UploadFile(
            filename="test.jpg",
            file=io.BytesIO(b"fake image content")
        )

        with patch('app.services.file_service.ensure_upload_directories'), \
             patch('aiofiles.open', create=True), \
             patch.object(upload_file, 'read', return_value=b"x" * (6 * 1024 * 1024)):  # 6MB

            with pytest.raises(HTTPException) as exc_info:
                await file_service.save_profile_image(upload_file, user_id=1)

            assert exc_info.value.status_code == 400
            assert "File size exceeds" in str(exc_info.value.detail)


class TestFileOperations:
    """파일 운영 관련 테스트"""

    @pytest.mark.asyncio
    async def test_delete_profile_image_success(self):
        """프로필 이미지 삭제 성공 테스트"""
        file_url = "/uploads/profile_images/test.jpg"

        with patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:
            mock_file_path = mock_profile_dir.__truediv__.return_value
            mock_file_path.exists.return_value = True
            mock_file_path.unlink = AsyncMock()

            result = await file_service.delete_profile_image(file_url)

            assert result == True
            mock_file_path.unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_profile_image_not_exists(self):
        """존재하지 않는 프로필 이미지 삭제 테스트"""
        file_url = "/uploads/profile_images/nonexistent.jpg"

        with patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:
            mock_file_path = mock_profile_dir.__truediv__.return_value
            mock_file_path.exists.return_value = False

            result = await file_service.delete_profile_image(file_url)

            assert result == False

    @pytest.mark.asyncio
    async def test_delete_profile_image_invalid_url(self):
        """잘못된 URL로 프로필 이미지 삭제 테스트"""
        file_url = "/invalid/path/test.jpg"

        result = await file_service.delete_profile_image(file_url)

        assert result == False

    @pytest.mark.asyncio
    async def test_get_file_info_success(self):
        """파일 정보 조회 성공 테스트"""
        file_url = "/uploads/profile_images/test.jpg"

        with patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:
            mock_file_path = mock_profile_dir.__truediv__.return_value
            mock_file_path.exists.return_value = True

            mock_stat = AsyncMock()
            mock_stat.st_size = 1024
            mock_stat.st_ctime = 1640995200.0  # 2022-01-01
            mock_stat.st_mtime = 1640995200.0
            mock_file_path.stat.return_value = mock_stat

            result = await file_service.get_file_info(file_url)

            assert result is not None
            assert result["filename"] == "test.jpg"
            assert result["size"] == 1024

    @pytest.mark.asyncio
    async def test_get_file_info_not_exists(self):
        """존재하지 않는 파일 정보 조회 테스트"""
        file_url = "/uploads/profile_images/nonexistent.jpg"

        with patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:
            mock_file_path = mock_profile_dir.__truediv__.return_value
            mock_file_path.exists.return_value = False

            result = await file_service.get_file_info(file_url)

            assert result is None

    def test_get_upload_stats(self):
        """업로드 통계 조회 테스트"""
        with patch('app.services.file_service.ensure_upload_directories'), \
             patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:

            # 가짜 파일들 생성
            mock_files = []
            for i in range(3):
                mock_file = AsyncMock()
                mock_file.stat.return_value.st_size = 1024 * (i + 1)
                mock_files.append(mock_file)

            mock_profile_dir.glob.return_value = mock_files

            stats = file_service.get_upload_stats()

            assert stats["profile_images_count"] == 3
            assert stats["profile_images_size"] == 1024 + 2048 + 3072  # 1+2+3 KB
            assert stats["total_files"] == 3

    def test_get_upload_stats_empty(self):
        """빈 디렉토리 업로드 통계 조회 테스트"""
        with patch('app.services.file_service.ensure_upload_directories'), \
             patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:

            mock_profile_dir.glob.return_value = []

            stats = file_service.get_upload_stats()

            assert stats["profile_images_count"] == 0
            assert stats["profile_images_size"] == 0
            assert stats["total_files"] == 0

    def test_get_upload_stats_error(self):
        """업로드 통계 조회 오류 테스트"""
        with patch('app.services.file_service.ensure_upload_directories'), \
             patch('app.services.file_service.PROFILE_IMAGES_DIR') as mock_profile_dir:

            mock_profile_dir.glob.side_effect = Exception("디렉토리 접근 오류")

            stats = file_service.get_upload_stats()

            # 오류 발생 시 기본값 반환
            assert stats["profile_images_count"] == 0
            assert stats["profile_images_size"] == 0
            assert stats["total_files"] == 0


class TestCleanupOperations:
    """정리 작업 테스트"""

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_files(self):
        """고아 파일 정리 테스트"""
        # 현재는 기본 구현만 있음
        result = await file_service.cleanup_orphaned_files()

        assert result == 0  # 기본 반환값