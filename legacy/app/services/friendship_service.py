"""
친구 관계 관리 서비스 (Friendship Service)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================

이 모듈은 사용자 간의 친구 관계를 관리하는 서비스입니다.
친구 요청, 수락, 거절 등의 기능을 제공하며,
MySQL 데이터베이스와 SQLAlchemy ORM을 사용합니다.

친구 관계 상태 (Friendship Status):
- pending: 친구 요청 대기 중
- accepted: 친구 관계 성립

관계 저장 규칙:
- user_id_1: 친구 요청을 보낸 사용자 (requester)
- user_id_2: 친구 요청을 받은 사용자 (target)
- 양방향 검색을 위해 양쪽 ID로 조회 필요

================================================================================
적용된 디자인 패턴 (Design Patterns Applied)
================================================================================

1. Service Layer Pattern (서비스 레이어 패턴)
   - 비즈니스 로직을 서비스 클래스에 캡슐화
   - API 레이어와 데이터 접근 레이어 분리
   - 트랜잭션 경계 관리

2. Static Service Pattern (정적 서비스 패턴)
   - 모든 메서드가 @staticmethod
   - 상태를 가지지 않음 (Stateless)
   - 수평 확장에 유리

3. Soft Delete Pattern (소프트 삭제 패턴)
   - 실제 삭제 대신 deleted_at 타임스탬프 설정
   - 데이터 복구 가능, 감사 추적 용이
   - 쿼리 시 deleted_at IS NULL 조건 필수

4. Bidirectional Query Pattern (양방향 쿼리 패턴)
   - 친구 관계는 (A→B) 또는 (B→A)로 저장
   - 검색 시 양방향 OR 조건 사용
   - find_friendship() 메서드에서 구현

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================

1. Single Responsibility Principle (단일 책임 원칙)
   - FriendshipService: 친구 관계 관리만 담당
   - 사용자 검색은 별도 로직 (search_users_for_friend)

2. Open/Closed Principle (개방-폐쇄 원칙)
   - 새로운 친구 관계 상태 추가 시 기존 코드 최소 수정
   - 검증 로직을 메서드별로 분리

3. Interface Segregation Principle (인터페이스 분리 원칙)
   - 친구 요청/수락/거절/취소 각각 별도 메서드
   - 클라이언트는 필요한 기능만 사용

4. Dependency Inversion Principle (의존성 역전 원칙)
   - AsyncSession을 파라미터로 주입
   - 테스트 시 Mock Session 사용 가능

================================================================================
데이터베이스 설계 (Database Design)
================================================================================

Friendship 테이블:
+-------------+----------+---------------------------------+
| Column      | Type     | Description                     |
+-------------+----------+---------------------------------+
| id          | INT PK   | 고유 식별자                      |
| user_id_1   | INT FK   | 요청자 (requester)              |
| user_id_2   | INT FK   | 대상자 (target)                 |
| status      | VARCHAR  | 상태 (pending/accepted)         |
| created_at  | DATETIME | 요청 생성 시간                   |
| updated_at  | DATETIME | 마지막 수정 시간                 |
| deleted_at  | DATETIME | 삭제 시간 (soft delete)         |
+-------------+----------+---------------------------------+

인덱스 권장:
- (user_id_1, user_id_2, status, deleted_at)
- (user_id_2, status, deleted_at)  -- 받은 요청 조회용

================================================================================
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from legacy.app.models.friendships import Friendship
from legacy.app.models.users import User
from legacy.app.schemas.friendship import FriendshipCreate


class FriendshipService:
    """
    친구 관계 관리 서비스 클래스

    =========================================================================
    클래스 설계 철학
    =========================================================================

    1. Stateless 설계
       - 모든 메서드가 @staticmethod
       - 인스턴스 생성 없이 사용
       - db 세션을 파라미터로 전달

    2. 트랜잭션 관리
       - 각 메서드에서 commit() 호출
       - 호출자가 트랜잭션 제어 가능
       - 필요시 refresh()로 최신 데이터 조회

    3. 예외 처리 전략
       - ValueError: 비즈니스 규칙 위반
       - SQLAlchemy 예외: 호출자에게 전파

    =========================================================================
    사용 예시
    =========================================================================

    # 친구 요청 전송
    friendship = await FriendshipService.send_friend_request(
        db=session,
        requester_id=1,
        target_id=2
    )

    # 친구 요청 수락
    friendship = await FriendshipService.accept_friend_request(
        db=session,
        friendship_id=friendship.id,
        user_id=2  # 요청받은 사용자만 수락 가능
    )

    # 친구 목록 조회
    friends = await FriendshipService.get_friends_list(db=session, user_id=1)
    """

    @staticmethod
    async def send_friend_request(
        db: AsyncSession,
        requester_id: int,
        target_id: int
    ) -> Friendship:
        """
        친구 요청을 전송합니다.

        =====================================================================
        비즈니스 규칙
        =====================================================================

        1. 자기 자신에게 요청 불가 (API 레이어에서 검증 권장)
        2. 이미 친구이거나 요청 중이면 거부
        3. 차단 상태 확인 (별도 BlockUser 테이블)

        =====================================================================
        동작 흐름
        =====================================================================

        1. 기존 친구 관계 확인 (양방향 검색)
        2. 관계가 없으면 새 Friendship 생성
        3. status = "pending"으로 설정
        4. DB에 저장 및 반환

        =====================================================================
        SOLID 적용: Single Responsibility
        =====================================================================

        - 친구 요청 전송만 담당
        - 차단 확인은 별도 서비스/메서드에서
        - 알림 발송은 호출자가 처리

        Args:
            db: 데이터베이스 세션 (AsyncSession)
            requester_id: 요청자 ID (친구 요청을 보내는 사용자)
            target_id: 대상자 ID (친구 요청을 받는 사용자)

        Returns:
            Friendship: 생성된 친구 요청 객체

        Raises:
            ValueError: 이미 친구 관계가 존재하거나 요청 중인 경우

        Example:
            >>> friendship = await FriendshipService.send_friend_request(
            ...     db=session,
            ...     requester_id=1,
            ...     target_id=2
            ... )
            >>> print(friendship.status)
            "pending"
        """
        # =====================================================================
        # Step 1: 기존 친구 관계 확인 (양방향 검색)
        # =====================================================================
        # (1→2) 또는 (2→1) 형태의 관계가 있는지 확인
        existing = await FriendshipService.find_friendship(db, requester_id, target_id)
        if existing:
            # 이미 관계가 존재함 (pending, accepted 모두 포함)
            raise ValueError("Friendship already exists or pending")

        # =====================================================================
        # Step 2: 새 친구 요청 생성
        # =====================================================================
        friendship = Friendship(
            user_id_1=requester_id,  # 요청자
            user_id_2=target_id,     # 대상자
            status="pending",        # 대기 상태
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # =====================================================================
        # Step 3: DB 저장
        # =====================================================================
        db.add(friendship)
        await db.commit()
        await db.refresh(friendship)  # 생성된 ID 등 최신 데이터 조회

        return friendship

    @staticmethod
    async def find_friendship(
        db: AsyncSession,
        user_id_1: int,
        user_id_2: int
    ) -> Optional[Friendship]:
        """
        두 사용자 간의 친구 관계를 찾습니다 (양방향 검색).

        =====================================================================
        양방향 검색 (Bidirectional Query)
        =====================================================================

        친구 관계는 한 방향으로만 저장됨:
        - A가 B에게 요청: (user_id_1=A, user_id_2=B)
        - B가 A에게 요청: (user_id_1=B, user_id_2=A)

        따라서 두 경우 모두 검색해야 함:
        ```sql
        WHERE (user_id_1 = A AND user_id_2 = B)
           OR (user_id_1 = B AND user_id_2 = A)
        ```

        =====================================================================
        Soft Delete 고려
        =====================================================================

        deleted_at이 NULL인 레코드만 조회
        삭제된 관계는 검색에서 제외

        Args:
            db: 데이터베이스 세션
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            Optional[Friendship]: 친구 관계 객체 또는 None

        Example:
            >>> # A와 B 사이의 관계 검색 (요청 방향 무관)
            >>> friendship = await FriendshipService.find_friendship(
            ...     db=session,
            ...     user_id_1=1,
            ...     user_id_2=2
            ... )
            >>> if friendship:
            ...     print(f"관계 상태: {friendship.status}")
        """
        # ---------------------------------------------------------------------
        # SQLAlchemy Query 구성
        #
        # and_(): AND 조건 그룹
        # or_(): OR 조건 그룹
        #
        # 최종 쿼리:
        # WHERE deleted_at IS NULL
        #   AND ((user_id_1 = ? AND user_id_2 = ?)
        #        OR (user_id_1 = ? AND user_id_2 = ?))
        # ---------------------------------------------------------------------
        query = select(Friendship).where(
            and_(
                Friendship.deleted_at.is_(None),  # Soft delete 필터
                or_(
                    # 정방향: user_id_1 → user_id_2
                    and_(Friendship.user_id_1 == user_id_1, Friendship.user_id_2 == user_id_2),
                    # 역방향: user_id_2 → user_id_1
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
        친구 요청을 수락합니다 (friendship_id 기반).

        =====================================================================
        권한 검증 (Authorization)
        =====================================================================

        요청을 받은 사용자(user_id_2)만 수락 가능
        - user_id_1은 요청자 (수락 권한 없음)
        - user_id_2가 user_id와 일치해야 함

        =====================================================================
        상태 검증 (State Validation)
        =====================================================================

        pending 상태에서만 수락 가능
        - accepted: 이미 친구
        - 기타 상태: 잘못된 요청

        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 요청 ID
            user_id: 수락하는 사용자 ID (현재 사용자)

        Returns:
            Friendship: 업데이트된 친구 관계 (status="accepted")

        Raises:
            ValueError:
                - 친구 요청을 찾을 수 없음
                - 수락 권한이 없음 (요청받은 사용자가 아님)
                - 이미 처리된 요청 (pending 상태가 아님)

        Example:
            >>> # 친구 요청 수락
            >>> friendship = await FriendshipService.accept_friend_request(
            ...     db=session,
            ...     friendship_id=123,
            ...     user_id=2  # 요청받은 사용자
            ... )
            >>> print(friendship.status)
            "accepted"
        """
        # Step 1: 친구 요청 조회
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        # Step 2: 권한 검증 (요청받은 사용자만 수락 가능)
        if friendship.user_id_2 != user_id:
            raise ValueError("Only the target user can accept the request")

        # Step 3: 상태 검증 (pending 상태에서만 수락 가능)
        if friendship.status != "pending":
            raise ValueError("Friendship request is not pending")

        # Step 4: 상태 업데이트
        friendship.status = "accepted"
        friendship.updated_at = datetime.utcnow()

        # Step 5: DB 저장
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
        친구 요청을 거절합니다 (Soft Delete).

        =====================================================================
        Soft Delete Pattern
        =====================================================================

        실제 삭제 대신 deleted_at 타임스탬프 설정
        - 데이터 복구 가능
        - 감사 추적 (audit trail) 용이
        - 분석/통계에 활용 가능

        거절 후 재요청:
        - deleted_at이 설정된 레코드는 find_friendship()에서 제외
        - 새로운 친구 요청 가능

        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 요청 ID
            user_id: 거절하는 사용자 ID

        Returns:
            bool: 거절 성공 여부

        Raises:
            ValueError:
                - 친구 요청을 찾을 수 없음
                - 거절 권한이 없음
                - pending 상태가 아님

        Example:
            >>> success = await FriendshipService.reject_friend_request(
            ...     db=session,
            ...     friendship_id=123,
            ...     user_id=2
            ... )
            >>> print(success)
            True
        """
        # Step 1: 친구 요청 조회
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        # Step 2: 권한 검증 (요청받은 사용자만 거절 가능)
        if friendship.user_id_2 != user_id:
            raise ValueError("Only the target user can reject the request")

        # Step 3: 상태 검증
        if friendship.status != "pending":
            raise ValueError("Friendship request is not pending")

        # Step 4: Soft Delete
        friendship.deleted_at = datetime.utcnow()
        friendship.updated_at = datetime.utcnow()

        await db.commit()

        return True

    @staticmethod
    async def accept_friend_request_by_requester(
        db: AsyncSession,
        requester_user_id: int,
        current_user_id: int
    ) -> Friendship:
        """
        요청자 ID로 친구 요청을 수락합니다.

        =====================================================================
        사용 시나리오
        =====================================================================

        friendship_id를 모르는 경우:
        - "사용자 A의 친구 요청을 수락"
        - 모바일 앱에서 친구 요청 알림 클릭 시

        accept_friend_request()와의 차이:
        - 이 메서드: 요청자 ID로 검색
        - 그 메서드: friendship ID로 직접 조회

        Args:
            db: 데이터베이스 세션
            requester_user_id: 친구 요청을 보낸 사용자 ID
            current_user_id: 수락하는 사용자 ID (현재 사용자)

        Returns:
            Friendship: 업데이트된 친구 관계

        Raises:
            ValueError: 친구 요청을 찾을 수 없거나 이미 처리됨

        Example:
            >>> # "사용자 ID=5의 친구 요청 수락"
            >>> friendship = await FriendshipService.accept_friend_request_by_requester(
            ...     db=session,
            ...     requester_user_id=5,
            ...     current_user_id=10
            ... )
        """
        # ---------------------------------------------------------------------
        # 특정 조건의 친구 요청 검색
        #
        # 조건:
        # - user_id_1 = 요청자 (requester)
        # - user_id_2 = 현재 사용자 (수락자)
        # - status = "pending"
        # - deleted_at IS NULL
        # ---------------------------------------------------------------------
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

        # 상태 업데이트
        friendship.status = "accepted"
        friendship.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(friendship)

        return friendship

    @staticmethod
    async def reject_friend_request_by_requester(
        db: AsyncSession,
        requester_user_id: int,
        current_user_id: int
    ) -> bool:
        """
        요청자 ID로 친구 요청을 거절합니다 (Soft Delete).

        accept_friend_request_by_requester()의 거절 버전

        Args:
            db: 데이터베이스 세션
            requester_user_id: 친구 요청을 보낸 사용자 ID
            current_user_id: 거절하는 사용자 ID (현재 사용자)

        Returns:
            bool: 거절 성공 여부

        Raises:
            ValueError: 친구 요청을 찾을 수 없거나 이미 처리됨
        """
        # 요청자가 보낸 pending 상태의 친구 요청 찾기
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

        # Soft Delete
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
        자신이 보낸 친구 요청을 취소합니다 (Soft Delete).

        =====================================================================
        수락/거절 vs 취소
        =====================================================================

        수락/거절: 요청받은 사용자(user_id_2)의 권한
        취소: 요청보낸 사용자(user_id_1)의 권한

        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 요청 ID
            user_id: 취소하는 사용자 ID (요청을 보낸 사용자)

        Returns:
            bool: 취소 성공 여부

        Raises:
            ValueError:
                - 친구 요청을 찾을 수 없음
                - 취소 권한이 없음 (요청을 보낸 사용자가 아님)
                - pending 상태가 아님

        Example:
            >>> # 내가 보낸 친구 요청 취소
            >>> success = await FriendshipService.cancel_friend_request(
            ...     db=session,
            ...     friendship_id=123,
            ...     user_id=1  # 요청을 보낸 사용자
            ... )
        """
        # Step 1: 친구 요청 조회
        friendship = await FriendshipService.get_friendship_by_id(db, friendship_id)
        if not friendship:
            raise ValueError("Friendship not found")

        # Step 2: 권한 검증 (요청을 보낸 사용자만 취소 가능)
        if friendship.user_id_1 != user_id:
            raise ValueError("Only the requester can cancel the request")

        # Step 3: 상태 검증 (pending 상태에서만 취소 가능)
        if friendship.status != "pending":
            raise ValueError("Only pending requests can be cancelled")

        # Step 4: Soft Delete
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
        대상 유저 ID로 자신이 보낸 친구 요청을 취소합니다 (Soft Delete).

        =====================================================================
        사용 시나리오
        =====================================================================

        friendship_id를 모르는 경우:
        - "사용자 B에게 보낸 친구 요청 취소"
        - 친구 추가 UI에서 요청 취소 버튼 클릭 시

        Args:
            db: 데이터베이스 세션
            requester_id: 요청을 보낸 사용자 ID (현재 사용자)
            target_user_id: 요청을 받은 대상 사용자 ID

        Returns:
            bool: 취소 성공 여부

        Raises:
            ValueError: 친구 요청을 찾을 수 없거나 이미 처리됨
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

        # Soft Delete
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

        =====================================================================
        Soft Delete 고려
        =====================================================================

        deleted_at이 NULL인 레코드만 조회
        삭제된 관계는 조회 불가

        =====================================================================
        버그 수정 이력
        =====================================================================

        수정 전 (버그):
        ```python
        Friendship.user_id_1 == friendship_id  # 잘못된 필드!
        ```

        수정 후:
        ```python
        Friendship.id == friendship_id  # 올바른 필드
        ```

        Args:
            db: 데이터베이스 세션
            friendship_id: 친구 관계 ID

        Returns:
            Optional[Friendship]: 친구 관계 객체 또는 None

        Example:
            >>> friendship = await FriendshipService.get_friendship_by_id(
            ...     db=session,
            ...     friendship_id=123
            ... )
        """
        query = select(Friendship).where(
            and_(
                Friendship.id == friendship_id,  # 버그 수정: user_id_1 -> id
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

        =====================================================================
        조인 전략 (Join Strategy)
        =====================================================================

        Friendship과 User 테이블 조인:
        - 사용자가 user_id_1이면 → User는 user_id_2
        - 사용자가 user_id_2이면 → User는 user_id_1

        이를 하나의 쿼리로 처리하기 위해 OR 조건 사용

        =====================================================================
        반환 데이터
        =====================================================================

        List of (User, created_at):
        - User: 친구의 사용자 정보
        - created_at: 친구 관계 시작일 (Friendship.created_at)

        =====================================================================
        성능 고려
        =====================================================================

        대량의 친구가 있는 경우 페이지네이션 권장
        현재는 전체 조회 (향후 limit/offset 추가 가능)

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID

        Returns:
            List[Tuple[User, datetime]]: (친구 정보, 친구 관계 시작일) 목록

        Example:
            >>> friends = await FriendshipService.get_friends_list(
            ...     db=session,
            ...     user_id=1
            ... )
            >>> for friend, since in friends:
            ...     print(f"{friend.username}과 {since}부터 친구")
        """
        # ---------------------------------------------------------------------
        # 복잡한 조인 쿼리
        #
        # 1. Friendship과 User 조인
        # 2. 현재 사용자가 user_id_1이면 user_id_2의 User 조인
        # 3. 현재 사용자가 user_id_2이면 user_id_1의 User 조인
        # 4. status = "accepted" (친구 관계만)
        # 5. deleted_at IS NULL (삭제되지 않은)
        # ---------------------------------------------------------------------
        query = select(Friendship, User).join(
            User,
            or_(
                # 내가 요청을 보낸 경우: 상대방 = user_id_2
                and_(Friendship.user_id_1 == user_id, User.id == Friendship.user_id_2),
                # 내가 요청을 받은 경우: 상대방 = user_id_1
                and_(Friendship.user_id_2 == user_id, User.id == Friendship.user_id_1)
            )
        ).where(
            and_(
                Friendship.status == "accepted",  # 수락된 관계만
                Friendship.deleted_at.is_(None),  # 삭제되지 않은
                or_(
                    Friendship.user_id_1 == user_id,
                    Friendship.user_id_2 == user_id
                )
            )
        )

        result = await db.execute(query)
        friends = []

        # 결과 처리: (Friendship, User) 튜플에서 필요한 정보 추출
        for friendship, user in result.all():
            friends.append((user, friendship.created_at))

        return friends

    @staticmethod
    async def get_friend_requests(
        db: AsyncSession,
        user_id: int
    ) -> Tuple[List[Tuple[Friendship, User]], List[Tuple[Friendship, User]]]:
        """
        사용자의 친구 요청 목록을 조회합니다 (받은 요청 + 보낸 요청).

        =====================================================================
        반환 구조
        =====================================================================

        Tuple[받은 요청, 보낸 요청]
        - 받은 요청: 내가 user_id_2인 경우 (수락/거절 권한 있음)
        - 보낸 요청: 내가 user_id_1인 경우 (취소 권한 있음)

        각 요청은 (Friendship, User) 튜플:
        - Friendship: 친구 요청 정보 (id, status, created_at 등)
        - User: 상대방 사용자 정보

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID

        Returns:
            Tuple[받은 요청 리스트, 보낸 요청 리스트]

        Example:
            >>> received, sent = await FriendshipService.get_friend_requests(
            ...     db=session,
            ...     user_id=1
            ... )
            >>> print(f"받은 요청: {len(received)}개")
            >>> print(f"보낸 요청: {len(sent)}개")
        """
        # =====================================================================
        # 받은 요청 쿼리 (Received Requests)
        # =====================================================================
        # 내가 user_id_2 = 요청을 받은 사용자
        # User 조인: user_id_1 = 요청을 보낸 사용자 정보
        received_query = select(Friendship, User).join(
            User, User.id == Friendship.user_id_1
        ).where(
            and_(
                Friendship.user_id_2 == user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )

        # =====================================================================
        # 보낸 요청 쿼리 (Sent Requests)
        # =====================================================================
        # 내가 user_id_1 = 요청을 보낸 사용자
        # User 조인: user_id_2 = 요청을 받은 사용자 정보
        sent_query = select(Friendship, User).join(
            User, User.id == Friendship.user_id_2
        ).where(
            and_(
                Friendship.user_id_1 == user_id,
                Friendship.status == "pending",
                Friendship.deleted_at.is_(None)
            )
        )

        # 두 쿼리 실행
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

        =====================================================================
        사용 시나리오
        =====================================================================

        1. 채팅방 생성 전 친구 확인
        2. 프로필 조회 시 친구 상태 표시
        3. 권한 확인 (친구만 볼 수 있는 콘텐츠)

        Args:
            db: 데이터베이스 세션
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            bool: 친구 여부 (True=친구, False=친구 아님)

        Example:
            >>> is_friend = await FriendshipService.are_friends(
            ...     db=session,
            ...     user_id_1=1,
            ...     user_id_2=2
            ... )
            >>> if is_friend:
            ...     print("친구입니다")
        """
        # 양방향 검색으로 친구 관계 조회
        friendship = await FriendshipService.find_friendship(db, user_id_1, user_id_2)
        # 관계가 존재하고 status가 "accepted"인 경우만 친구
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

        검색 조건:
        1. 이미 친구인 사용자 제외
        2. 본인 제외
        3. 활성 사용자만 (is_active = True)
        4. email 또는 username으로 검색 (LIKE)

        Args:
            db: 데이터베이스 세션
            current_user_id: 현재 사용자 ID
            query: 검색어 (email 또는 username)
            limit: 결과 제한 개수 (기본값: 20)

        Returns:
            List[User]: 검색된 사용자 목록
        """
        # Step 1: 이미 친구인 사용자 ID 목록 조회
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

        # Step 2: 제외할 사용자 ID 목록 (친구 + 본인)
        excluded_ids = friend_ids | {current_user_id}

        # Step 3: 사용자 검색 (email 또는 username)
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
