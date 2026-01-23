from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.friendships import Friendship
from app.models.users import User
from app.schemas.friendship import FriendshipCreate


class FriendshipService:
    """친구 관계 관리 서비스"""

    @staticmethod
    async def send_friend_request(
        db: AsyncSession,
        requester_id: int,
        target_id: int
    ) -> Friendship:
        """
        친구 요청을 전송합니다.
        
        Args:
            db: 데이터베이스 세션
            requester_id: 요청자 ID
            target_id: 대상자 ID
            
        Returns:
            Friendship: 생성된 친구 요청
        """
        # 기존 친구 관계 확인 (양방향)
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
        
        return friendship

    @staticmethod
    async def find_friendship(
        db: AsyncSession,
        user_id_1: int,
        user_id_2: int
    ) -> Optional[Friendship]:
        """
        두 사용자 간의 친구 관계를 찾습니다 (양방향 검색).
        
        Args:
            db: 데이터베이스 세션
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID
            
        Returns:
            Optional[Friendship]: 친구 관계 또는 None
        """
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
    async def accept_friend_request(
        db: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> Friendship:
        """
        친구 요청을 수락합니다.
        
        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 요청 ID
            user_id: 수락하는 사용자 ID
            
        Returns:
            Friendship: 업데이트된 친구 관계
        """
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")
        
        # 요청 받은 사용자만 수락 가능
        if friendship.user_id_2 != user_id:
            raise ValueError("Only the target user can accept the request")
        
        if friendship.status != "pending":
            raise ValueError("Friendship request is not pending")
        
        friendship.status = "accepted"
        friendship.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(friendship)
        
        return friendship

    @staticmethod
    async def reject_friend_request(
        db: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> bool:
        """
        친구 요청을 거절합니다 (soft delete).

        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 요청 ID
            user_id: 거절하는 사용자 ID

        Returns:
            bool: 거절 성공 여부
        """
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        # 요청 받은 사용자만 거절 가능
        if friendship.user_id_2 != user_id:
            raise ValueError("Only the target user can reject the request")

        if friendship.status != "pending":
            raise ValueError("Friendship request is not pending")

        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()

        return True

    @staticmethod
    async def cancel_friend_request(
        db: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> bool:
        """
        자신이 보낸 친구 요청을 취소합니다 (soft delete).

        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 요청 ID
            user_id: 취소하는 사용자 ID (요청을 보낸 사용자)

        Returns:
            bool: 취소 성공 여부
        """
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        # 요청을 보낸 사용자만 취소 가능
        if friendship.user_id_1 != user_id:
            raise ValueError("Only the requester can cancel the request")

        if friendship.status != "pending":
            raise ValueError("Only pending requests can be cancelled")

        # Soft delete
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
        """
        대상 유저 ID로 자신이 보낸 친구 요청을 취소합니다 (soft delete).

        Args:
            db: 데이터베이스 세션
            requester_id: 요청을 보낸 사용자 ID (현재 사용자)
            target_user_id: 요청을 받은 대상 사용자 ID

        Returns:
            bool: 취소 성공 여부
        """
        # 현재 사용자가 보낸 pending 상태의 친구 요청 찾기
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

        # Soft delete
        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()

        return True

    @staticmethod
    async def get_friendship_by_id(
        db: AsyncSession,
        friendship_id: int
    ) -> Optional[Friendship]:
        """
        친구 관계를 ID로 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 관계 ID
            
        Returns:
            Optional[Friendship]: 친구 관계 또는 None
        """
        query = select(Friendship).where(
            and_(
                Friendship.user_id_1 == friendship_id,
                Friendship.deleted_at.is_(None)
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_friends_list(
        db: AsyncSession,
        user_id: int
    ) -> List[Tuple[User, datetime]]:
        """
        사용자의 친구 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            
        Returns:
            List[Tuple[User, datetime]]: (친구 정보, 친구 관계 시작일) 목록
        """
        query = select(Friendship, User).join(
            User,
            or_(
                and_(Friendship.user_id_1 == user_id, User.id == Friendship.user_id_2),
                and_(Friendship.user_id_2 == user_id, User.id == Friendship.user_id_1)
            )
        ).where(
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
        friends = []
        
        for friendship, user in result.all():
            friends.append((user, friendship.created_at))
        
        return friends

    @staticmethod
    async def get_friend_requests(
        db: AsyncSession,
        user_id: int
    ) -> Tuple[List[Tuple[Friendship, User]], List[Tuple[Friendship, User]]]:
        """
        사용자의 친구 요청 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            
        Returns:
            Tuple[받은 요청, 보낸 요청]: 각각 (Friendship, User) 리스트
        """
        # 받은 요청
        received_query = select(Friendship, User).join(
            User, User.id == Friendship.user_id_1
        ).where(
            and_(
                Friendship.user_id_2 == user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        
        # 보낸 요청
        sent_query = select(Friendship, User).join(
            User, User.id == Friendship.user_id_2
        ).where(
            and_(
                Friendship.user_id_1 == user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )
        
        received_result = await db.execute(received_query)
        sent_result = await db.execute(sent_query)
        
        received_requests = received_result.all()
        sent_requests = sent_result.all()
        
        return received_requests, sent_requests

    @staticmethod
    async def are_friends(
        db: AsyncSession,
        user_id_1: int,
        user_id_2: int
    ) -> bool:
        """
        두 사용자가 친구인지 확인합니다.

        Args:
            db: 데이터베이스 세션
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            bool: 친구 여부
        """
        friendship = await FriendshipService.find_friendship(db, user_id_1, user_id_2)
        return friendship is not None and friendship.status == "accepted"

    @staticmethod
    async def search_users_for_friend(
        db: AsyncSession,
        current_user_id: int,
        query: str,
        limit: int = 20
    ) -> List[User]:
        """
        친구 추가를 위한 사용자 검색

        조건:
        - 최소 3글자 이상 입력
        - 이미 친구인 사용자 제외
        - 차단한/차단된 사용자 제외
        - 본인 제외

        Args:
            db: 데이터베이스 세션
            current_user_id: 현재 사용자 ID
            query: 검색어 (email 또는 username)
            limit: 결과 제한 개수

        Returns:
            List[User]: 검색된 사용자 목록
        """
        from app.models.block_users import BlockUser

        # 이미 친구인 사용자 ID 목록
        friends_query = select(Friendship.user_id_1, Friendship.user_id_2).where(
            and_(
                Friendship.status == "accepted",
                Friendship.deleted_at.is_(None),
                or_(
                    Friendship.user_id_1 == current_user_id,
                    Friendship.user_id_2 == current_user_id
                )
            )
        )
        friends_result = await db.execute(friends_query)
        friend_ids = set()
        for row in friends_result.all():
            friend_ids.add(row.user_id_1 if row.user_id_1 != current_user_id else row.user_id_2)

        # 차단한/차단된 사용자 ID 목록
        block_query = select(BlockUser.user_id, BlockUser.blocked_user_id).where(
            or_(
                BlockUser.user_id == current_user_id,
                BlockUser.blocked_user_id == current_user_id
            )
        )
        block_result = await db.execute(block_query)
        blocked_ids = set()
        for row in block_result.all():
            blocked_ids.add(row.user_id if row.user_id != current_user_id else row.blocked_user_id)

        # 제외할 사용자 ID 목록 (친구 + 차단 + 본인)
        excluded_ids = friend_ids | blocked_ids | {current_user_id}

        # 사용자 검색 (email 또는 username)
        search_pattern = f"%{query}%"
        user_query = select(User).where(
            and_(
                User.is_active == True,
                User.id.notin_(excluded_ids) if excluded_ids else True,
                or_(
                    User.email.ilike(search_pattern),
                    User.username.ilike(search_pattern)
                )
            )
        ).limit(limit)

        result = await db.execute(user_query)
        return result.scalars().all()