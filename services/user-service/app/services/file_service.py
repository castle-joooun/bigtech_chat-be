"""
File upload service layer for handling file operations.

Handles file uploads, validations, and storage operations.
"""

import os
import uuid
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from pathlib import Path
import aiofiles

from app.core.config import settings


# =============================================================================
# File Upload Configuration
# =============================================================================

# 허용된 이미지 파일 확장자
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# 최대 파일 크기 (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

# 업로드 디렉토리
UPLOAD_DIR = Path("uploads")
PROFILE_IMAGES_DIR = UPLOAD_DIR / "profile_images"


# =============================================================================
# File Utilities
# =============================================================================

def ensure_upload_directories():
    """업로드 디렉토리들이 존재하는지 확인하고 생성"""
    UPLOAD_DIR.mkdir(exist_ok=True)
    PROFILE_IMAGES_DIR.mkdir(exist_ok=True)


def get_file_extension(filename: str) -> str:
    """파일 확장자 추출"""
    return Path(filename).suffix.lower()


def is_allowed_image_file(filename: str) -> bool:
    """허용된 이미지 파일인지 확인"""
    return get_file_extension(filename) in ALLOWED_IMAGE_EXTENSIONS


def generate_unique_filename(original_filename: str) -> str:
    """고유한 파일명 생성"""
    extension = get_file_extension(original_filename)
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{extension}"


def validate_file_size(file_size: int) -> bool:
    """파일 크기 검증"""
    return file_size <= MAX_FILE_SIZE


# =============================================================================
# File Upload Operations
# =============================================================================

async def validate_uploaded_file(file: UploadFile) -> None:
    """업로드된 파일 검증"""

    # 파일 존재 확인
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # 파일 확장자 검증
    if not is_allowed_image_file(file.filename):
        allowed_extensions = ", ".join(ALLOWED_IMAGE_EXTENSIONS)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed extensions: {allowed_extensions}"
        )

    # 파일 크기 검증
    if hasattr(file, 'size') and file.size:
        if not validate_file_size(file.size):
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024*1024)}MB"
            )


async def save_profile_image(file: UploadFile, user_id: int) -> str:
    """프로필 이미지 저장"""

    # 파일 검증
    await validate_uploaded_file(file)

    # 업로드 디렉토리 확인
    ensure_upload_directories()

    # 고유한 파일명 생성
    unique_filename = generate_unique_filename(file.filename)
    file_path = PROFILE_IMAGES_DIR / unique_filename

    try:
        # 파일 저장
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()

            # 실제 파일 크기 검증
            if not validate_file_size(len(content)):
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024*1024)}MB"
                )

            await f.write(content)

        # 상대 URL 반환 (서버의 기본 URL + 파일 경로)
        return f"/uploads/profile_images/{unique_filename}"

    except Exception as e:
        # 저장 실패 시 파일 삭제
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


async def delete_profile_image(file_url: str) -> bool:
    """프로필 이미지 삭제"""
    try:
        # URL에서 파일 경로 추출
        if file_url.startswith("/uploads/profile_images/"):
            filename = file_url.split("/")[-1]
            file_path = PROFILE_IMAGES_DIR / filename

            # 파일 존재 확인 후 삭제
            if file_path.exists():
                file_path.unlink()
                return True

        return False

    except Exception:
        return False


async def get_file_info(file_url: str) -> Optional[dict]:
    """파일 정보 조회"""
    try:
        if file_url.startswith("/uploads/profile_images/"):
            filename = file_url.split("/")[-1]
            file_path = PROFILE_IMAGES_DIR / filename

            if file_path.exists():
                stat = file_path.stat()
                return {
                    "filename": filename,
                    "size": stat.st_size,
                    "created_at": stat.st_ctime,
                    "modified_at": stat.st_mtime
                }

        return None

    except Exception:
        return None
