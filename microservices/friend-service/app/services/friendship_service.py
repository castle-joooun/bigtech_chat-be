"""
Friendship Service Layer (친구 관계 서비스 레이어)
=================================================

친구 관계 관리를 위한 비즈니스 로직을 담당합니다.

MSA 원칙 적용
--------------
- User 데이터는 user-service API를 통해 조회
- Friendship 테이블만 직접 DB 접근
- FK 제약조건 제거 (user_id만 정수로 저장)

Domain-Driven Design (DDD)
--------------------------
이 서비스는 Friendship Aggregate를 관리합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                  Friendship Aggregate                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Friendship (Aggregate Root)                         │   │
│  │ - id (PK)                                           │   │
│  │ - user_id_1 (요청자)                                 │   │
│  │ - user_id_2 (대상자)                                 │   │
│  │ - status (pending, accepted)                        │   │
│  │ - created_at, updated_at, deleted_at               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

관련 파일
---------
- app/api/friend.py: API 엔드포인트
- app/models/friendship.py: Friendship 모델
- app/services/auth_service.py: user-service API 클라이언트
"""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.friendship import Friendship
from app.services.cache_service import get_friend_cache
from app.services import auth_service
from shared_lib.schemas.user import UserProfile


class FriendshipService:
    """
    친구 관계 관리 서비스

    Design Pattern: Static Factory Methods
        - 모든 메서드가 @staticmethod
        - 인스턴스 생성 불필요
        - 테스트 용이성

    메서드 분류:
        1. 친구 요청 관련: send, accept, reject, cancel
        2. 조회 관련: find, get_friends_list, get_friend_requests
        3. 검증 관련: are_friends
    """

    # =========================================================================
    # 친구 요청 전송
    # =========================================================================

    @staticmethod
    async def send_friend_request(
        db: AsyncSession,
        requester_id: int,
        target_id: int
    ) -> Friendship:
        """
        친구 요청 전송

        Args:
            db: 데이터베이스 세션
            requester_id: 요청자 ID (user_id_1)
            target_id: 대상자 ID (user_id_2)

        Returns:
            Friendship: 생성된 친구 요청

        Raises:
            ValueError: 이미 친구 관계가 존재하거나 pending 상태인 경우
        """
        # 기존 친구 관계 확인 (양방향 검색)
        existing = await FriendshipService.find_friendship(db, requester_id, target_id)
        if existing:
            raise ValueError("Friendship already exists or pending")

        # 새 친구 요청 생성
        friendship = Friendship(
            user_id_1=requester_id,
            user_id_2=target_id,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(friendship)
        await db.commit()
        await db.refresh(friendship)

        # 캐시 무효화
        friend_cache = get_friend_cache()
        if friend_cache:
            await friend_cache.invalidate_requests(requester_id)
            await friend_cache.invalidate_requests(target_id)

        return friendship

    # =========================================================================
    # 친구 관계 조회
    # =========================================================================

    @staticmethod
    async def find_friendship(
        db: AsyncSession,
        user_id_1: int,
        user_id_2: int
    ) -> Optional[Friendship]:
        """두 사용자 간의 친구 관계 조회 (양방향)"""
        query = select(Friendship).where(
            and_(
                Friendship.deleted_at.is_(None),
                or_(
                    and_(Friendship.user_id_1 == user_id_1, Friendship.user_id_2 == user_id_2),
                    and_(Friendship.user_id_1 == user_id_2, Friendship.user_id_2 == user_id_1)
                )
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_friendship_by_id(
        db: AsyncSession,
        friendship_id: int
    ) -> Optional[Friendship]:
        """친구 관계를 ID로 조회"""
        query = select(Friendship).where(
            and_(
                Friendship.id == friendship_id,
                Friendship.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    # =========================================================================
    # 친구 요청 수락
    # =========================================================================

    @staticmethod
    async def accept_friend_request(
        db: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> Friendship:
        """친구 요청 수락 (ID로)"""
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        if friendship.user_id_2 != user_id:
            raise ValueError("Only the target user can accept the request")

        if friendship.status != "pending":
            raise ValueError("Friendship request is not pending")

        friendship.status = "accepted"
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(friendship)

        # 캐시 무효화
        friend_cache = get_friend_cache()
        if friend_cache:
            await friend_cache.invalidate_friendship(friendship.user_id_1, friendship.user_id_2)

        return friendship

    @staticmethod
    async def accept_friend_request_by_requester(
        db: AsyncSession,
        requester_user_id: int,
        current_user_id: int
    ) -> Friendship:
        """친구 요청 수락 (요청자 ID로)"""
        query = select(Friendship).where(
            and_(
                Friendship.user_id_1 == requester_user_id,
                Friendship.user_id_2 == current_user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        friendship = result.scalar_one_or_none()

        if not friendship:
            raise ValueError("Friend request not found or already processed")

        friendship.status = "accepted"
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(friendship)

        # 캐시 무효화
        friend_cache = get_friend_cache()
        if friend_cache:
            await friend_cache.invalidate_friendship(requester_user_id, current_user_id)

        return friendship

    # =========================================================================
    # 친구 요청 거절
    # =========================================================================

    @staticmethod
    async def reject_friend_request(
        db: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> bool:
        """친구 요청 거절 (Soft Delete)"""
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        if friendship.user_id_2 != user_id:
            raise ValueError("Only the target user can reject the request")

        if friendship.status != "pending":
            raise ValueError("Friendship request is not pending")

        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def reject_friend_request_by_requester(
        db: AsyncSession,
        requester_user_id: int,
        current_user_id: int
    ) -> bool:
        """친구 요청 거절 (요청자 ID로)"""
        query = select(Friendship).where(
            and_(
                Friendship.user_id_1 == requester_user_id,
                Friendship.user_id_2 == current_user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        friendship = result.scalar_one_or_none()

        if not friendship:
            raise ValueError("Friend request not found or already processed")

        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        return True

    # =========================================================================
    # 친구 요청 취소
    # =========================================================================

    @staticmethod
    async def cancel_friend_request(
        db: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> bool:
        """친구 요청 취소 (요청자가 자신의 요청 취소)"""
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        if friendship.user_id_1 != user_id:
            raise ValueError("Only the requester can cancel the request")

        if friendship.status != "pending":
            raise ValueError("Only pending requests can be cancelled")

        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def cancel_friend_request_by_target(
        db: AsyncSession,
        requester_id: int,
        target_user_id: int
    ) -> bool:
        """친구 요청 취소 (대상 사용자 ID로)"""
        query = select(Friendship).where(
            and_(
                Friendship.user_id_1 == requester_id,
                Friendship.user_id_2 == target_user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        friendship = result.scalar_one_or_none()

        if not friendship:
            raise ValueError("Friend request not found or already processed")

        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        return True

    # =========================================================================
    # 친구 목록 및 요청 목록 조회
    # =========================================================================

    @staticmethod
    async def get_friends_list(
        db: AsyncSession,
        user_id: int
    ) -> List[Tuple[UserProfile, datetime]]:
        """
        친구 목록 조회 (user-service API 호출)

        Args:
            db: 데이터베이스 세션
            user_id: 조회할 사용자 ID

        Returns:
            List[Tuple[UserProfile, datetime]]:
                - UserProfile: 친구 정보 (user-service에서 조회)
                - datetime: 친구 관계 생성일
        """
        # 캐시 조회
        friend_cache = get_friend_cache()
        if friend_cache:
            cached = await friend_cache.get_friends_list(user_id)
            if cached is not None:
                return cached

        # Friendship 레코드 조회 (User JOIN 없이)
        query = select(Friendship).where(
            and_(
                Friendship.status == "accepted",
                Friendship.deleted_at.is_(None),
                or_(
                    Friendship.user_id_1 == user_id,
                    Friendship.user_id_2 == user_id
                )
            )
        )
        result = await db.execute(query)
        friendships = result.scalars().all()

        # 친구 ID 추출
        friend_ids = []
        friendship_map: Dict[int, datetime] = {}  # friend_id -> created_at
        for f in friendships:
            friend_id = f.user_id_2 if f.user_id_1 == user_id else f.user_id_1
            friend_ids.append(friend_id)
            friendship_map[friend_id] = f.created_at

        # user-service API로 사용자 정보 Batch 조회
        users = await auth_service.get_users_by_ids(friend_ids)

        # 결과 조합
        friends = []
        for user in users:
            created_at = friendship_map.get(user.id)
            friends.append((user, created_at))

        # 캐시 저장
        if friend_cache and friends:
            friends_dict = [
                {
                    "user_id": u.id,
                    "username": u.username,
                    "display_name": u.display_name,
                    "is_online": u.is_online,
                    "created_at": dt.isoformat() if dt else None
                }
                for u, dt in friends
            ]
            await friend_cache.set_friends_list(user_id, friends_dict)

        return friends

    @staticmethod
    async def get_friend_requests(
        db: AsyncSession,
        user_id: int
    ) -> Tuple[List[Tuple[Friendship, UserProfile]], List[Tuple[Friendship, UserProfile]]]:
        """
        친구 요청 목록 조회 (받은 요청 + 보낸 요청)

        Args:
            db: 데이터베이스 세션
            user_id: 조회할 사용자 ID

        Returns:
            Tuple[received, sent]:
                - received: 받은 요청 리스트 [(Friendship, UserProfile), ...]
                - sent: 보낸 요청 리스트 [(Friendship, UserProfile), ...]
        """
        # 받은 요청 조회
        received_query = select(Friendship).where(
            and_(
                Friendship.user_id_2 == user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        received_result = await db.execute(received_query)
        received_friendships = received_result.scalars().all()

        # 보낸 요청 조회
        sent_query = select(Friendship).where(
            and_(
                Friendship.user_id_1 == user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        sent_result = await db.execute(sent_query)
        sent_friendships = sent_result.scalars().all()

        # 요청자/대상자 ID 수집
        requester_ids = [f.user_id_1 for f in received_friendships]
        target_ids = [f.user_id_2 for f in sent_friendships]
        all_user_ids = list(set(requester_ids + target_ids))

        # user-service API로 Batch 조회
        users = await auth_service.get_users_by_ids(all_user_ids)
        user_map = {u.id: u for u in users}

        # 결과 조합
        received_requests = []
        for f in received_friendships:
            requester = user_map.get(f.user_id_1)
            if requester:
                received_requests.append((f, requester))

        sent_requests = []
        for f in sent_friendships:
            target = user_map.get(f.user_id_2)
            if target:
                sent_requests.append((f, target))

        return received_requests, sent_requests

    # =========================================================================
    # 친구 관계 검증
    # =========================================================================

    @staticmethod
    async def are_friends(
        db: AsyncSession,
        user_id_1: int,
        user_id_2: int
    ) -> bool:
        """
        두 사용자가 친구인지 확인 (캐시 적용)

        Args:
            db: 데이터베이스 세션
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            bool: 친구 여부 (accepted 상태인 경우 True)
        """
        # 캐시 조회
        friend_cache = get_friend_cache()
        if friend_cache:
            cached = await friend_cache.get_are_friends(user_id_1, user_id_2)
            if cached is not None:
                return cached

        # DB 조회
        friendship = await FriendshipService.find_friendship(db, user_id_1, user_id_2)
        are_friends = friendship is not None and friendship.status == "accepted"

        # 캐시 저장
        if friend_cache:
            await friend_cache.set_are_friends(user_id_1, user_id_2, are_friends)

        return are_friends
