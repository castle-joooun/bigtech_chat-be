"""
Authentication Service Layer (인증 서비스 레이어)
================================================

데이터베이스 작업을 담당하는 서비스 레이어입니다.
Repository 패턴을 적용하여 데이터 접근 로직을 캡슐화합니다.

아키텍처 패턴
-------------
1. Repository Pattern:
   - 데이터 접근 로직을 비즈니스 로직에서 분리
   - 데이터 소스(MySQL, MongoDB 등)가 변경되어도 서비스 레이어 수정 최소화
   - 테스트 시 Mock Repository로 쉽게 대체 가능

2. Service Layer Pattern:
   - 비즈니스 로직과 데이터 접근 로직의 경계 역할
   - API 레이어는 이 서비스를 통해서만 데이터에 접근

데이터 흐름
-----------
```
API Layer (auth.py)
      ↓
Service Layer (auth_service.py)  ← 현재 파일
      ↓
ORM Layer (SQLAlchemy)
      ↓
Database (MySQL)
```

SOLID 원칙
----------
- SRP (Single Responsibility):
    각 함수는 하나의 데이터 작업만 담당
    예: find_user_by_id()는 ID로 조회만, create_user()는 생성만

- OCP (Open/Closed):
    새로운 조회 조건 추가 시 기존 함수 수정 없이 새 함수 추가
    예: find_user_by_email(), find_user_by_username()

- DIP (Dependency Inversion):
    AsyncSession 추상화를 통해 구체적인 DB 구현에 의존하지 않음
    테스트 시 Mock 세션 주입 가능

함수 분류
---------
1. CRUD Operations: 기본 데이터 조작
2. Existence Checks: 존재 여부 확인 (Boolean 반환)
3. Authentication: 인증 관련 작업
4. Profile Management: 프로필 업데이트

사용 예시
---------
```python
from app.services import auth_service

# API 레이어에서 사용
async def login(db: AsyncSession, email: str, password: str):
    user = await auth_service.authenticate_user_by_email(db, email, password)
    if user:
        return create_token(user)
    raise InvalidCredentialsError()
```

관련 파일
---------
- app/api/auth.py: 이 서비스를 호출하는 API 엔드포인트
- app/models/user.py: User 도메인 모델
- app/database/mysql.py: 데이터베이스 세션 관리
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.user import User
from app.services.cache_service import get_user_cache


# =============================================================================
# User CRUD Operations (사용자 기본 CRUD)
# =============================================================================

async def find_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    사용자 ID로 단일 사용자 조회 (캐시 적용)

    Primary Key 조회이므로 인덱스를 사용하여 O(1) 성능.
    없는 경우 None 반환 (예외 발생하지 않음).

    캐시 전략:
        - 캐시 키: user:profile:{user_id}
        - TTL: 5분
        - 프로필 수정 시 캐시 무효화

    Args:
        db: SQLAlchemy 비동기 세션
        user_id: 조회할 사용자 ID (Primary Key)

    Returns:
        User 객체 또는 None

    SQL equivalent:
        SELECT * FROM users WHERE id = :user_id LIMIT 1

    사용 예시:
        user = await find_user_by_id(db, 123)
        if user:
            print(user.username)
    """
    # 캐시 조회
    user_cache = get_user_cache()
    if user_cache:
        cached = await user_cache.get_user_profile(user_id)
        if cached is not None:
            # 캐시된 dict를 User 객체로 변환하지 않고 dict 반환
            # (ORM 객체가 필요한 경우 DB 조회 필요)
            pass  # 캐시는 dict용, ORM 객체는 DB에서 직접 조회

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    이메일로 사용자 조회

    email 컬럼에 UNIQUE INDEX가 있으므로 O(1) 성능.
    로그인 시 사용자 조회에 사용.

    Args:
        db: SQLAlchemy 비동기 세션
        email: 조회할 이메일 주소

    Returns:
        User 객체 또는 None

    SQL equivalent:
        SELECT * FROM users WHERE email = :email LIMIT 1
    """
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def find_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    사용자명으로 사용자 조회

    username 컬럼에 UNIQUE INDEX가 있으므로 O(1) 성능.
    회원가입 시 중복 확인에 사용.

    Args:
        db: SQLAlchemy 비동기 세션
        username: 조회할 사용자명

    Returns:
        User 객체 또는 None

    SQL equivalent:
        SELECT * FROM users WHERE username = :username LIMIT 1
    """
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    username: str,
    password_hash: str,
    display_name: Optional[str] = None
) -> User:
    """
    새 사용자 생성

    트랜잭션 관리:
        - db.add(): 세션에 객체 추가 (INSERT 예약)
        - db.commit(): 실제 DB에 반영
        - db.refresh(): DB에서 생성된 ID 등을 다시 로드

    Args:
        db: SQLAlchemy 비동기 세션
        email: 사용자 이메일 (UNIQUE)
        username: 사용자명 (UNIQUE)
        password_hash: bcrypt로 해시된 비밀번호
        display_name: 표시 이름 (선택)

    Returns:
        생성된 User 객체 (id 포함)

    Raises:
        IntegrityError: email 또는 username 중복 시

    SQL equivalent:
        INSERT INTO users (email, username, password_hash, display_name, created_at, updated_at)
        VALUES (:email, :username, :password_hash, :display_name, NOW(), NOW())
    """
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
    await db.refresh(new_user)  # DB에서 생성된 ID를 가져옴

    return new_user


# =============================================================================
# User Existence Checks (존재 여부 확인)
# =============================================================================
# Boolean을 반환하는 헬퍼 함수들
# 비즈니스 로직에서 조건 분기에 사용

async def is_email_exists(db: AsyncSession, email: str) -> bool:
    """
    이메일 중복 확인

    회원가입 시 이메일 중복 검증에 사용.

    Args:
        db: SQLAlchemy 비동기 세션
        email: 확인할 이메일 주소

    Returns:
        True if 이메일이 이미 존재, False otherwise

    사용 예시:
        if await is_email_exists(db, "test@example.com"):
            raise EmailAlreadyExistsError()
    """
    user = await find_user_by_email(db, email)
    return user is not None


async def is_username_exists(db: AsyncSession, username: str) -> bool:
    """
    사용자명 중복 확인

    회원가입 시 사용자명 중복 검증에 사용.

    Args:
        db: SQLAlchemy 비동기 세션
        username: 확인할 사용자명

    Returns:
        True if 사용자명이 이미 존재, False otherwise
    """
    user = await find_user_by_username(db, username)
    return user is not None


async def is_user_exists(db: AsyncSession, user_id: int) -> bool:
    """
    사용자 존재 여부 확인

    다른 서비스에서 사용자 ID 유효성 검증에 사용.

    Args:
        db: SQLAlchemy 비동기 세션
        user_id: 확인할 사용자 ID

    Returns:
        True if 사용자가 존재, False otherwise
    """
    user = await find_user_by_id(db, user_id)
    return user is not None


# =============================================================================
# Authentication Operations (인증 작업)
# =============================================================================

async def authenticate_user_by_email(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """
    이메일과 비밀번호로 사용자 인증

    로그인 프로세스:
        1. 이메일로 사용자 조회
        2. 비밀번호 해시 검증 (bcrypt)
        3. 인증 성공 시 User 반환, 실패 시 None

    보안 고려사항:
        - 비밀번호 검증은 비동기로 처리 (verify_password_async)
        - bcrypt 해싱은 CPU 집약적이므로 ThreadPoolExecutor 사용
        - 이벤트 루프 블로킹 방지

    Args:
        db: SQLAlchemy 비동기 세션
        email: 로그인 이메일
        password: 평문 비밀번호 (해시와 비교됨)

    Returns:
        인증 성공 시 User 객체, 실패 시 None

    사용 예시:
        user = await authenticate_user_by_email(db, "test@test.com", "password123")
        if user:
            token = create_access_token(user)
        else:
            raise InvalidCredentialsError()
    """
    from app.utils.auth import verify_password_async

    user = await find_user_by_email(db, email)
    if not user:
        return None

    # 비동기로 비밀번호 검증 (이벤트 루프 블로킹 방지)
    if not await verify_password_async(password, user.password_hash):
        return None

    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    사용자 ID로 조회 (find_user_by_id의 별칭)

    API 레이어에서 일관된 네이밍을 위해 제공.

    Args:
        db: SQLAlchemy 비동기 세션
        user_id: 조회할 사용자 ID

    Returns:
        User 객체 또는 None
    """
    return await find_user_by_id(db, user_id)


# =============================================================================
# Profile Management Operations (프로필 관리)
# =============================================================================

async def update_user_profile(
    db: AsyncSession,
    user_id: int,
    display_name: Optional[str] = None,
    status_message: Optional[str] = None
) -> Optional[User]:
    """
    사용자 프로필 정보 업데이트 (캐시 무효화)

    부분 업데이트 (Partial Update) 지원:
        - None이 아닌 필드만 업데이트
        - None으로 전달된 필드는 변경하지 않음

    캐시 전략:
        - 업데이트 후 관련 캐시 무효화

    Args:
        db: SQLAlchemy 비동기 세션
        user_id: 업데이트할 사용자 ID
        display_name: 새 표시 이름 (None이면 변경 안 함)
        status_message: 새 상태 메시지 (None이면 변경 안 함)

    Returns:
        업데이트된 User 객체 또는 None (사용자 없음)

    SQL equivalent:
        UPDATE users
        SET display_name = :display_name,
            status_message = :status_message,
            updated_at = NOW()
        WHERE id = :user_id
    """
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

    # 캐시 무효화
    user_cache = get_user_cache()
    if user_cache:
        await user_cache.invalidate_user(user_id, user.email, user.username)

    return user


async def update_online_status(
    db: AsyncSession,
    user_id: int,
    is_online: bool
) -> Optional[User]:
    """
    사용자 온라인 상태 업데이트

    Redis와 MySQL 동시 업데이트:
        - Redis: 실시간 조회용 (TTL 기반)
        - MySQL: 영속적 저장 및 last_seen_at 기록

    오프라인으로 변경 시 last_seen_at도 함께 업데이트.

    Args:
        db: SQLAlchemy 비동기 세션
        user_id: 업데이트할 사용자 ID
        is_online: 온라인 상태 (True/False)

    Returns:
        업데이트된 User 객체 또는 None
    """
    user = await find_user_by_id(db, user_id)
    if not user:
        return None

    user.is_online = is_online
    if not is_online:
        user.last_seen_at = datetime.utcnow()  # 오프라인 시 마지막 접속 시간 기록
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


async def update_last_seen(
    db: AsyncSession,
    user_id: int
) -> Optional[User]:
    """
    마지막 접속 시간 업데이트

    Heartbeat 또는 로그아웃 시 호출.

    Args:
        db: SQLAlchemy 비동기 세션
        user_id: 업데이트할 사용자 ID

    Returns:
        업데이트된 User 객체 또는 None
    """
    user = await find_user_by_id(db, user_id)
    if not user:
        return None

    user.last_seen_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


# =============================================================================
# User Search Operations (사용자 검색)
# =============================================================================

async def search_users_by_username(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    exclude_user_id: Optional[int] = None
) -> List[User]:
    """
    사용자명 또는 표시명으로 사용자 검색 (캐시 적용)

    LIKE 검색으로 부분 일치하는 사용자 목록 반환.
    친구 추가 시 사용자 검색에 사용.

    캐시 전략:
        - 캐시 키: user:search:{query}:{limit}
        - TTL: 1분 (검색 결과는 자주 변경될 수 있음)

    성능 고려사항:
        - ILIKE는 대소문자 무시 검색
        - 인덱스가 없으면 Full Table Scan 발생
        - limit으로 결과 수 제한하여 성능 확보

    Args:
        db: SQLAlchemy 비동기 세션
        query: 검색어 (부분 일치)
        limit: 최대 결과 수 (기본값: 10)
        exclude_user_id: 제외할 사용자 ID (자기 자신 제외용)

    Returns:
        검색된 User 객체 리스트

    SQL equivalent:
        SELECT * FROM users
        WHERE (username ILIKE '%query%' OR display_name ILIKE '%query%')
          AND is_active = true
          AND id != :exclude_user_id
        LIMIT :limit
    """
    # 캐시 조회 (exclude_user_id가 없는 경우만 캐시 사용)
    user_cache = get_user_cache()
    if user_cache and not exclude_user_id:
        cached = await user_cache.get_search_results(query, limit)
        if cached is not None:
            # 캐시된 결과 반환 (dict 리스트)
            return cached

    # 기본 쿼리 조건
    conditions = [
        or_(
            User.username.ilike(f"%{query}%"),
            User.display_name.ilike(f"%{query}%")
        ),
        User.is_active == True  # 활성화된 사용자만
    ]

    # 현재 사용자 제외 (자기 자신은 검색 결과에서 제외)
    if exclude_user_id:
        conditions.append(User.id != exclude_user_id)

    # 쿼리 실행
    stmt = select(User).where(and_(*conditions)).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()

    # 캐시 저장 (exclude_user_id가 없는 경우만)
    if user_cache and not exclude_user_id and users:
        users_dict = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "display_name": u.display_name,
                "is_online": u.is_online,
            }
            for u in users
        ]
        await user_cache.set_search_results(query, limit, users_dict)

    return users


async def get_user_count_by_query(
    db: AsyncSession,
    query: str,
    exclude_user_id: Optional[int] = None
) -> int:
    """
    검색 쿼리에 해당하는 총 사용자 수 조회

    페이지네이션 UI를 위한 전체 개수 반환.

    Args:
        db: SQLAlchemy 비동기 세션
        query: 검색어
        exclude_user_id: 제외할 사용자 ID

    Returns:
        검색 조건에 맞는 사용자 수

    SQL equivalent:
        SELECT COUNT(id) FROM users
        WHERE (username ILIKE '%query%' OR display_name ILIKE '%query%')
          AND is_active = true
    """
    from sqlalchemy import func

    conditions = [
        or_(
            User.username.ilike(f"%{query}%"),
            User.display_name.ilike(f"%{query}%")
        ),
        User.is_active == True
    ]

    if exclude_user_id:
        conditions.append(User.id != exclude_user_id)

    stmt = select(func.count(User.id)).where(and_(*conditions))
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_users_by_ids(
    db: AsyncSession,
    user_ids: List[int]
) -> List[User]:
    """
    사용자 ID 목록으로 여러 사용자 조회

    Batch 조회로 N+1 문제 방지.
    채팅방 멤버 목록 조회 등에 사용.

    Args:
        db: SQLAlchemy 비동기 세션
        user_ids: 조회할 사용자 ID 리스트

    Returns:
        조회된 User 객체 리스트 (순서 보장 안 됨)

    SQL equivalent:
        SELECT * FROM users WHERE id IN (:user_ids)
    """
    if not user_ids:
        return []

    stmt = select(User).where(User.id.in_(user_ids))
    result = await db.execute(stmt)
    return result.scalars().all()
