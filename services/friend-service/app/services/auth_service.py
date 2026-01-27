"""
Authentication service layer for database operations.

Handles all database queries and data operations related to user authentication and profile management.
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.user import User


# =============================================================================
# User CRUD Operations
# =============================================================================

async def find_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """사용자 ID로 조회"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """이메일로 사용자 조회"""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def find_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """사용자명으로 사용자 조회"""
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    username: str,
    password_hash: str,
    display_name: Optional[str] = None
) -> User:
    """새 사용자 생성"""
    from datetime import datetime

    new_user = User(
        email=email,
        username=username,
        password_hash=password_hash,
        display_name=display_name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


# =============================================================================
# User Existence Checks (Boolean Functions)
# =============================================================================

async def is_email_exists(db: AsyncSession, email: str) -> bool:
    """이메일이 이미 존재하는지 확인"""
    user = await find_user_by_email(db, email)
    return user is not None


async def is_username_exists(db: AsyncSession, username: str) -> bool:
    """사용자명이 이미 존재하는지 확인"""
    user = await find_user_by_username(db, username)
    return user is not None


async def is_user_exists(db: AsyncSession, user_id: int) -> bool:
    """사용자가 존재하는지 확인"""
    user = await find_user_by_id(db, user_id)
    return user is not None


# =============================================================================
# Authentication Operations
# =============================================================================

async def authenticate_user_by_email(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """이메일과 비밀번호로 사용자 인증"""
    from app.utils.auth import verify_password

    user = await find_user_by_email(db, email)
    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """사용자 ID로 조회"""
    return await find_user_by_id(db, user_id)


# =============================================================================
# Profile Management Operations
# =============================================================================

async def update_user_profile(
    db: AsyncSession,
    user_id: int,
    display_name: Optional[str] = None,
    status_message: Optional[str] = None
) -> Optional[User]:
    """사용자 프로필 정보 업데이트"""
    user = await find_user_by_id(db, user_id)
    if not user:
        return None

    if display_name is not None:
        user.display_name = display_name
    if status_message is not None:
        user.status_message = status_message

    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


async def update_profile_image(
    db: AsyncSession,
    user_id: int,
    profile_image_url: str
) -> Optional[User]:
    """프로필 이미지 URL 업데이트"""
    user = await find_user_by_id(db, user_id)
    if not user:
        return None

    user.profile_image_url = profile_image_url
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


async def update_online_status(
    db: AsyncSession,
    user_id: int,
    is_online: bool
) -> Optional[User]:
    """사용자 온라인 상태 업데이트"""
    user = await find_user_by_id(db, user_id)
    if not user:
        return None

    user.is_online = is_online
    if not is_online:
        user.last_seen_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


async def update_last_seen(
    db: AsyncSession,
    user_id: int
) -> Optional[User]:
    """마지막 접속 시간 업데이트"""
    user = await find_user_by_id(db, user_id)
    if not user:
        return None

    user.last_seen_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


async def search_users_by_username(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    exclude_user_id: Optional[int] = None
) -> List[User]:
    """사용자명으로 사용자 검색"""

    # 기본 쿼리 조건
    conditions = [
        or_(
            User.username.ilike(f"%{query}%"),
            User.display_name.ilike(f"%{query}%")
        ),
        User.is_active == True  # 활성화된 사용자만
    ]

    # 현재 사용자 제외
    if exclude_user_id:
        conditions.append(User.id != exclude_user_id)

    # 쿼리 실행
    stmt = select(User).where(and_(*conditions)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_user_count_by_query(
    db: AsyncSession,
    query: str,
    exclude_user_id: Optional[int] = None
) -> int:
    """검색 쿼리에 해당하는 사용자 수 조회"""
    from sqlalchemy import func

    # 기본 쿼리 조건
    conditions = [
        or_(
            User.username.ilike(f"%{query}%"),
            User.display_name.ilike(f"%{query}%")
        ),
        User.is_active == True  # 활성화된 사용자만
    ]

    # 현재 사용자 제외
    if exclude_user_id:
        conditions.append(User.id != exclude_user_id)

    # 쿼리 실행
    stmt = select(func.count(User.id)).where(and_(*conditions))
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_users_by_ids(
    db: AsyncSession,
    user_ids: List[int]
) -> List[User]:
    """사용자 ID 목록으로 사용자들 조회"""
    if not user_ids:
        return []

    stmt = select(User).where(User.id.in_(user_ids))
    result = await db.execute(stmt)
    return result.scalars().all()
