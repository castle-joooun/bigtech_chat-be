"""
메시지 서비스 레이어 (Message Service Layer)

================================================================================
아키텍처 패턴: Repository Pattern + Service Layer Pattern
================================================================================

이 모듈은 메시지 관련 비즈니스 로직과 데이터 접근을 담당합니다.

[설계 원칙 - SOLID]
- S (Single Responsibility): 메시지 도메인의 CRUD 및 관련 연산만 담당
- O (Open/Closed): 새로운 메시지 타입 추가 시 기존 코드 수정 없이 확장 가능
- L (Liskov Substitution): Message 모델의 서브타입이 동일하게 동작
- I (Interface Segregation): 기능별로 섹션 분리 (CRUD, Reactions, Read Status 등)
- D (Dependency Inversion): Beanie ODM 추상화에 의존, 구체적 DB 구현에 비의존

[디자인 패턴]
1. Repository Pattern: 데이터 접근 로직을 캡슐화
2. Factory Pattern: create_message()에서 Message 객체 생성
3. Soft Delete Pattern: 실제 삭제 대신 is_deleted 플래그 사용
4. Bulk Operations Pattern: 대량 데이터 처리 시 N+1 쿼리 방지

[성능 최적화 기법]
- Bulk Insert: insert_many()를 사용한 대량 삽입
- Query Optimization: MongoDB 인덱스 활용
- Lazy Loading: 필요한 데이터만 조회
- Pagination: skip/limit을 통한 페이지네이션

[MongoDB 특화 기능]
- Beanie ODM: Pydantic 기반 비동기 MongoDB ODM
- Text Search: $text 연산자를 활용한 전문 검색
- Aggregation: 통계 쿼리에 집계 파이프라인 활용

================================================================================
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
from pymongo import DESCENDING, TEXT

from legacy.app.models.messages import Message, MessageReadStatus


# =============================================================================
# Message CRUD Operations (메시지 기본 CRUD 연산)
# =============================================================================
#
# [패턴] Repository Pattern
# - 데이터 접근 로직을 비즈니스 로직과 분리
# - 테스트 용이성 향상 (Mock Repository로 대체 가능)
# - 데이터 소스 변경 시 이 레이어만 수정하면 됨
#
# [SOLID - Single Responsibility Principle]
# - 각 함수는 하나의 명확한 책임만 가짐
# - create_message: 생성, find_message_by_id: 조회, etc.
# =============================================================================

async def create_message(
    user_id: int,
    room_id: int,
    room_type: str,
    content: str,
    message_type: str = "text",
    reply_to: Optional[str] = None,
    file_url: Optional[str] = None,
    file_name: Optional[str] = None,
    file_size: Optional[int] = None,
    file_type: Optional[str] = None
) -> Message:
    """
    메시지 생성 (Factory Pattern 적용)

    [디자인 패턴 - Factory Pattern]
    복잡한 객체 생성 로직을 캡슐화하여 클라이언트 코드를 단순화합니다.
    답장 메시지 정보 조회, 기본값 설정 등의 로직이 내부에서 처리됩니다.

    [작동 방식]
    1. 답장 대상 메시지가 있으면 해당 메시지 정보를 미리 조회
    2. 답장 내용은 100자로 제한하여 미리보기용으로 저장 (Denormalization)
    3. Message 도큐먼트 생성 및 MongoDB에 삽입

    [Denormalization 전략]
    reply_content, reply_sender_id를 메시지에 직접 저장하여
    조회 시 JOIN 없이 답장 정보를 바로 표시할 수 있음 (읽기 성능 최적화)

    Args:
        user_id: 메시지 작성자 ID
        room_id: 채팅방 ID
        room_type: 채팅방 타입 ("private" | "group")
        content: 메시지 내용
        message_type: 메시지 타입 ("text" | "image" | "file" | "system")
        reply_to: 답장 대상 메시지 ID (Optional)
        file_url: 첨부 파일 URL (Optional)
        file_name: 원본 파일명 (Optional)
        file_size: 파일 크기 bytes (Optional)
        file_type: 파일 MIME 타입 (Optional)

    Returns:
        Message: 생성된 메시지 도큐먼트

    Example:
        >>> message = await create_message(
        ...     user_id=1,
        ...     room_id=100,
        ...     room_type="private",
        ...     content="안녕하세요!"
        ... )
    """
    # -------------------------------------------------------------------------
    # Step 1: 답장 메시지 정보 조회 (Eager Loading for Denormalization)
    # -------------------------------------------------------------------------
    # 답장 기능 사용 시, 원본 메시지 정보를 미리 조회하여 저장
    # 이는 읽기 시점의 JOIN을 피하기 위한 의도적인 데이터 중복
    reply_content = None
    reply_sender_id = None

    if reply_to:
        reply_message = await find_message_by_id(reply_to)
        if reply_message:
            # 미리보기용으로 100자 제한 (UI 최적화)
            reply_content = (
                reply_message.content[:100] + "..."
                if len(reply_message.content) > 100
                else reply_message.content
            )
            reply_sender_id = reply_message.user_id

    # -------------------------------------------------------------------------
    # Step 2: Message 도큐먼트 생성 (Factory Pattern)
    # -------------------------------------------------------------------------
    # Beanie Document 모델을 사용하여 MongoDB 도큐먼트 생성
    message = Message(
        user_id=user_id,
        room_id=room_id,
        room_type=room_type,
        content=content,
        message_type=message_type,
        reply_to=reply_to,
        reply_content=reply_content,
        reply_sender_id=reply_sender_id,
        file_url=file_url,
        file_name=file_name,
        file_size=file_size,
        file_type=file_type,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    # -------------------------------------------------------------------------
    # Step 3: MongoDB에 삽입 (Beanie ODM의 비동기 insert)
    # -------------------------------------------------------------------------
    await message.insert()
    return message


async def find_message_by_id(message_id: str) -> Optional[Message]:
    """
    메시지 ID로 단일 조회

    [작동 방식]
    MongoDB의 _id 필드로 O(1) 조회 (Primary Key Index 활용)

    [예외 처리 전략 - Null Object Pattern 변형]
    잘못된 ObjectId 형식이나 존재하지 않는 메시지의 경우
    예외를 발생시키지 않고 None을 반환하여 호출자가 처리하도록 함

    Args:
        message_id: MongoDB ObjectId 문자열

    Returns:
        Optional[Message]: 메시지 도큐먼트 또는 None
    """
    try:
        # PydanticObjectId: 문자열을 MongoDB ObjectId로 변환
        return await Message.get(PydanticObjectId(message_id))
    except:
        # 잘못된 형식의 ID이거나 존재하지 않는 경우
        return None


async def get_room_messages(
    room_id: int,
    room_type: str = "private",
    limit: int = 50,
    skip: int = 0,
    include_deleted: bool = False
) -> List[Message]:
    """
    채팅방 메시지 목록 조회 (페이지네이션 지원)

    [디자인 패턴 - Query Builder Pattern]
    조건을 동적으로 구성하여 유연한 쿼리 생성

    [페이지네이션 전략 - Offset Pagination]
    skip/limit 방식 사용 (간단하지만 대용량에서는 Cursor 방식 권장)

    [정렬 전략]
    1. DB에서는 최신순(DESCENDING)으로 조회 (인덱스 활용)
    2. 결과를 역순으로 변환하여 시간순 정렬 (UI 요구사항)

    [인덱스 활용]
    복합 인덱스 사용: (room_id, room_type, created_at)

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입 (default: "private")
        limit: 조회할 메시지 수 (default: 50)
        skip: 건너뛸 메시지 수 - 페이지네이션용 (default: 0)
        include_deleted: 삭제된 메시지 포함 여부 (default: False)

    Returns:
        List[Message]: 시간순 정렬된 메시지 목록
    """
    # -------------------------------------------------------------------------
    # Step 1: 동적 쿼리 조건 구성 (Query Builder Pattern)
    # -------------------------------------------------------------------------
    conditions = [
        Message.room_id == room_id,
        Message.room_type == room_type
    ]

    # 소프트 삭제된 메시지 필터링 (기본적으로 제외)
    if not include_deleted:
        conditions.append(Message.is_deleted == False)

    # -------------------------------------------------------------------------
    # Step 2: 쿼리 실행 (Beanie의 Fluent API 활용)
    # -------------------------------------------------------------------------
    # sort: 최신순 정렬 (인덱스 활용을 위해 DESCENDING)
    # skip/limit: 페이지네이션
    # to_list(): 비동기로 결과를 리스트로 변환
    messages = await (
        Message.find(*conditions)
        .sort([("created_at", DESCENDING)])
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    # -------------------------------------------------------------------------
    # Step 3: 결과 정렬 변환 (UI 요구사항)
    # -------------------------------------------------------------------------
    # 채팅 UI에서는 오래된 메시지가 위에, 최신 메시지가 아래에 표시됨
    # DB 조회는 최신순(효율성), 반환은 시간순(UI 요구사항)
    return list(reversed(messages))


async def get_room_messages_count(
    room_id: int,
    room_type: str = "private",
    include_deleted: bool = False
) -> int:
    """
    채팅방 메시지 총 개수 조회

    [용도]
    - 페이지네이션 UI의 총 페이지 수 계산
    - "더 보기" 버튼 표시 여부 결정
    - 채팅방 통계 표시

    [성능]
    count() 메서드는 인덱스만 스캔하므로 전체 도큐먼트를 읽지 않음

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입
        include_deleted: 삭제된 메시지 포함 여부

    Returns:
        int: 메시지 총 개수
    """
    conditions = [
        Message.room_id == room_id,
        Message.room_type == room_type
    ]

    if not include_deleted:
        conditions.append(Message.is_deleted == False)

    return await Message.find(*conditions).count()


# =============================================================================
# Message Operations (메시지 조작 - 삭제, 수정, 복원)
# =============================================================================
#
# [패턴] Soft Delete Pattern
# - 실제 삭제 대신 is_deleted 플래그를 사용
# - 장점: 데이터 복구 가능, 감사 추적 용이, 참조 무결성 유지
# - 단점: 스토리지 사용량 증가, 쿼리 시 항상 필터링 필요
#
# [패턴] Command Pattern (간접적 적용)
# - 각 조작 함수가 하나의 명령을 캡슐화
# - 실행 취소(복원) 기능 제공
# =============================================================================

async def soft_delete_message(message_id: str, deleted_by_user_id: int) -> Optional[Message]:
    """
    메시지 소프트 삭제 (Soft Delete Pattern)

    [Soft Delete Pattern]
    물리적 삭제 대신 논리적 삭제를 수행합니다.
    - is_deleted: True로 설정
    - deleted_at: 삭제 시각 기록
    - deleted_by: 삭제 수행자 기록 (감사 추적용)

    [장점]
    1. 데이터 복구 가능 (restore_deleted_message 함수)
    2. 감사 로그 역할 (누가 언제 삭제했는지 추적)
    3. 외래 키 참조 무결성 유지 (다른 메시지가 이 메시지를 reply_to로 참조할 수 있음)

    [주의사항]
    조회 쿼리에서 항상 is_deleted == False 조건 필요

    Args:
        message_id: 삭제할 메시지 ID
        deleted_by_user_id: 삭제를 수행하는 사용자 ID

    Returns:
        Optional[Message]: 삭제 처리된 메시지 또는 None (메시지가 없는 경우)
    """
    message = await find_message_by_id(message_id)
    if not message:
        return None

    # Message 모델의 soft_delete 메서드 호출 (도메인 로직은 모델에)
    message.soft_delete(deleted_by_user_id)
    await message.save()
    return message


async def update_message_content(message_id: str, new_content: str) -> Optional[Message]:
    """
    메시지 내용 수정 (Edit History 보존)

    [수정 이력 관리]
    - is_edited: 수정 여부 플래그
    - edited_at: 수정 시각
    - original_content: 최초 원본 내용 보존 (첫 수정 시에만 저장)

    [비즈니스 규칙]
    - 삭제된 메시지는 수정 불가
    - 수정 후에도 원본 내용 접근 가능 (관리자/감사용)

    Args:
        message_id: 수정할 메시지 ID
        new_content: 새로운 메시지 내용

    Returns:
        Optional[Message]: 수정된 메시지 또는 None
    """
    message = await find_message_by_id(message_id)
    if not message or message.is_deleted:
        return None

    # Message 모델의 edit_content 메서드 호출
    message.edit_content(new_content)
    await message.save()
    return message


async def restore_deleted_message(message_id: str) -> Optional[Message]:
    """
    삭제된 메시지 복원

    [Soft Delete의 핵심 기능]
    소프트 삭제의 가장 큰 장점인 복원 기능을 제공합니다.

    [복원 조건]
    - 메시지가 존재해야 함
    - is_deleted가 True인 상태여야 함

    [복원 처리]
    - is_deleted: False로 변경
    - deleted_at, deleted_by: None으로 초기화
    - updated_at: 현재 시각으로 갱신

    Args:
        message_id: 복원할 메시지 ID

    Returns:
        Optional[Message]: 복원된 메시지 또는 None (조건 불충족 시)
    """
    message = await find_message_by_id(message_id)
    if not message or not message.is_deleted:
        return None

    # 삭제 관련 필드 초기화
    message.is_deleted = False
    message.deleted_at = None
    message.deleted_by = None
    message.updated_at = datetime.utcnow()

    await message.save()
    return message


# =============================================================================
# Message Read Status (메시지 읽음 상태 관리)
# =============================================================================
#
# [도메인 설계]
# 각 사용자가 각 메시지를 읽었는지 추적합니다.
# 읽음 확인("카카오톡 1" 같은) 기능의 기반입니다.
#
# [성능 최적화]
# - 벌크 연산으로 N+1 쿼리 문제 해결
# - 인덱스 최적화로 빠른 조회
# =============================================================================

async def mark_message_as_read(message_id: str, user_id: int, room_id: int) -> MessageReadStatus:
    """
    단일 메시지를 읽음으로 표시 (Idempotent)

    [멱등성]
    이미 읽음 처리된 메시지는 중복 생성하지 않고 기존 상태 반환

    Args:
        message_id: 읽은 메시지 ID
        user_id: 읽은 사용자 ID
        room_id: 채팅방 ID (조회 최적화용)

    Returns:
        MessageReadStatus: 읽음 상태 도큐먼트
    """
    # 기존 읽음 상태 확인 (멱등성 보장)
    existing_read = await MessageReadStatus.find_one(
        MessageReadStatus.message_id == message_id,
        MessageReadStatus.user_id == user_id
    )

    if existing_read:
        return existing_read

    # 새 읽음 상태 생성
    read_status = MessageReadStatus(
        message_id=message_id,
        user_id=user_id,
        room_id=room_id,
        read_at=datetime.utcnow()
    )

    await read_status.insert()
    return read_status


async def mark_multiple_messages_as_read(message_ids: List[str], user_id: int, room_id: int) -> int:
    """
    여러 메시지를 한 번에 읽음으로 표시 (Bulk Operation)

    ============================================================================
    [성능 최적화 - N+1 쿼리 문제 해결]
    ============================================================================

    [이전 방식의 문제점]
    ```python
    # Bad: N+1 Query Problem
    for message_id in message_ids:
        existing = await find_one(message_id)  # N번의 조회
        if not existing:
            await insert(read_status)          # N번의 삽입
    ```
    - 100개 메시지 = 200번의 DB 호출 (조회 100 + 삽입 100)

    [최적화된 방식]
    ```python
    # Good: Bulk Operations
    existing = await find_many(message_ids)    # 1번의 조회
    new_ids = filter(not in existing)
    await insert_many(new_statuses)            # 1번의 삽입
    ```
    - 100개 메시지 = 2번의 DB 호출 (조회 1 + 삽입 1)

    ============================================================================
    [작동 방식]
    ============================================================================
    1. 이미 읽음 처리된 메시지 ID들을 한 번에 조회 (IN 쿼리)
    2. 기존 읽음 목록에서 제외하여 새로 처리할 메시지 필터링
    3. 새 읽음 상태들을 insert_many로 한 번에 삽입

    [SOLID - Open/Closed Principle]
    벌크 연산 로직이 내부에 캡슐화되어 있어
    호출자는 단일/다중 처리 차이를 신경 쓸 필요 없음

    Args:
        message_ids: 읽음 처리할 메시지 ID 목록
        user_id: 읽은 사용자 ID
        room_id: 채팅방 ID

    Returns:
        int: 새로 읽음 처리된 메시지 수

    Example:
        >>> count = await mark_multiple_messages_as_read(
        ...     message_ids=["msg1", "msg2", "msg3"],
        ...     user_id=1,
        ...     room_id=100
        ... )
        >>> print(f"{count}개 메시지 읽음 처리됨")
    """
    # -------------------------------------------------------------------------
    # Step 0: 빈 입력 처리 (Early Return Pattern)
    # -------------------------------------------------------------------------
    if not message_ids:
        return 0

    # -------------------------------------------------------------------------
    # Step 1: 기존 읽음 상태 벌크 조회 (단일 쿼리)
    # -------------------------------------------------------------------------
    # IN 연산자를 사용하여 한 번의 쿼리로 모든 기존 상태 조회
    # 인덱스: (message_id) - 벌크 조회 최적화용
    existing_reads = await MessageReadStatus.find(
        MessageReadStatus.message_id.in_(message_ids),
        MessageReadStatus.user_id == user_id
    ).to_list()

    # Set으로 변환하여 O(1) 조회 (리스트 순회 O(n) 대비 성능 향상)
    existing_message_ids = {read.message_id for read in existing_reads}

    # -------------------------------------------------------------------------
    # Step 2: 새로 읽음 처리할 메시지 필터링
    # -------------------------------------------------------------------------
    # 이미 읽은 메시지는 제외하고 새로 처리할 것만 추출
    new_message_ids = [
        mid for mid in message_ids
        if mid not in existing_message_ids
    ]

    if not new_message_ids:
        return 0

    # -------------------------------------------------------------------------
    # Step 3: 벌크 삽입을 위한 도큐먼트 리스트 생성
    # -------------------------------------------------------------------------
    # 모든 도큐먼트에 동일한 타임스탬프 사용 (일관성)
    now = datetime.utcnow()
    new_read_statuses = [
        MessageReadStatus(
            message_id=message_id,
            user_id=user_id,
            room_id=room_id,
            read_at=now
        )
        for message_id in new_message_ids
    ]

    # -------------------------------------------------------------------------
    # Step 4: 벌크 삽입 실행 (단일 쿼리)
    # -------------------------------------------------------------------------
    # insert_many: MongoDB의 insertMany 명령어를 사용하여 한 번에 삽입
    # 네트워크 왕복 1회로 모든 삽입 완료
    if new_read_statuses:
        await MessageReadStatus.insert_many(new_read_statuses)

    return len(new_read_statuses)


async def get_unread_messages_count(room_id: int, user_id: int) -> int:
    """
    사용자의 읽지 않은 메시지 수 조회 (Optimized Query)

    ============================================================================
    [성능 최적화 - DB 레벨 필터링]
    ============================================================================

    [이전 방식의 문제점]
    ```python
    # Bad: 전체 데이터를 메모리로 로드 후 필터링
    all_messages = await Message.find(room_id=room_id).to_list()  # 전체 로드
    read_statuses = await ReadStatus.find(...).to_list()          # 전체 로드
    unread = [m for m in all_messages if m.id not in read_ids]    # 메모리 필터링
    return len(unread)
    ```
    - 채팅방에 10,000개 메시지가 있다면 10,000개 전부 로드
    - 메모리 사용량 급증, 네트워크 대역폭 낭비

    [최적화된 방식]
    ```python
    # Good: DB에서 바로 count
    return await Message.find(
        room_id=room_id,
        is_deleted=False,
        user_id != current_user,  # 내가 보낸 건 제외
        _id not in read_ids       # 읽은 것 제외
    ).count()  # DB에서 카운트만 반환
    ```
    - DB가 인덱스를 사용하여 효율적으로 계산
    - 실제 도큐먼트 데이터는 네트워크로 전송되지 않음

    ============================================================================
    [비즈니스 로직]
    ============================================================================
    읽지 않은 메시지 조건:
    1. 해당 채팅방의 메시지
    2. 삭제되지 않은 메시지
    3. 내가 보내지 않은 메시지 (자신이 보낸 메시지는 자동으로 읽음 처리)
    4. 아직 읽지 않은 메시지

    Args:
        room_id: 채팅방 ID
        user_id: 현재 사용자 ID

    Returns:
        int: 읽지 않은 메시지 수
    """
    # -------------------------------------------------------------------------
    # Step 1: 이미 읽은 메시지 ID 목록 조회
    # -------------------------------------------------------------------------
    # 인덱스: (room_id, user_id, read_at) - 효율적 조회
    read_statuses = await MessageReadStatus.find(
        MessageReadStatus.room_id == room_id,
        MessageReadStatus.user_id == user_id
    ).to_list()

    read_message_ids = [status.message_id for status in read_statuses]

    # -------------------------------------------------------------------------
    # Step 2: 읽지 않은 메시지 카운트 쿼리 구성
    # -------------------------------------------------------------------------
    conditions = [
        Message.room_id == room_id,
        Message.is_deleted == False,
        Message.user_id != user_id  # 자신이 보낸 메시지는 제외 (자동 읽음)
    ]

    # -------------------------------------------------------------------------
    # Step 3: 읽은 메시지 제외 조건 추가 ($nin 연산자)
    # -------------------------------------------------------------------------
    if read_message_ids:
        # 문자열 ID를 ObjectId로 변환
        from beanie import PydanticObjectId
        read_object_ids = []
        for mid in read_message_ids:
            try:
                read_object_ids.append(PydanticObjectId(mid))
            except:
                continue  # 잘못된 형식의 ID는 무시

        if read_object_ids:
            # $nin: Not In - 이 목록에 없는 것들만 조회
            conditions.append({"_id": {"$nin": read_object_ids}})

    # -------------------------------------------------------------------------
    # Step 4: DB에서 직접 카운트 (데이터 전송 없이 숫자만 반환)
    # -------------------------------------------------------------------------
    return await Message.find(*conditions).count()


async def get_message_read_status(message_id: str) -> List[MessageReadStatus]:
    """
    메시지의 읽음 상태 목록 조회

    [용도]
    - "읽음" 표시 (카카오톡의 숫자 표시 기능)
    - 읽은 사용자 목록 표시

    Args:
        message_id: 메시지 ID

    Returns:
        List[MessageReadStatus]: 해당 메시지를 읽은 모든 사용자 상태
    """
    return await MessageReadStatus.find(
        MessageReadStatus.message_id == message_id
    ).to_list()


# =============================================================================
# Message Search (메시지 검색 기능)
# =============================================================================
#
# [MongoDB Text Search]
# - $text 연산자를 사용한 전문 검색
# - 형태소 분석, 스테밍, 불용어 처리 지원
# - 텍스트 인덱스 필요: (content: "text", reply_content: "text")
#
# [디자인 패턴 - Specification Pattern 변형]
# 여러 검색 조건을 동적으로 조합하여 유연한 검색 지원
# =============================================================================

async def search_messages(
    query: str,
    user_id: Optional[int] = None,
    room_id: Optional[int] = None,
    message_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20,
    skip: int = 0
) -> List[Message]:
    """
    메시지 텍스트 검색 (Full-Text Search)

    [MongoDB Text Search 사용]
    $text 연산자는 MongoDB의 텍스트 인덱스를 활용하여
    효율적인 전문 검색을 수행합니다.

    [검색 기능]
    - 형태소 분석: "running"으로 "run", "runs" 등 검색 가능
    - 불용어 처리: "the", "a", "is" 등 무시
    - 언어 지원: 한국어 포함 다양한 언어 지원

    [필터 조합 - Specification Pattern]
    다양한 필터를 AND 조건으로 조합하여 정밀한 검색 지원

    Args:
        query: 검색 키워드
        user_id: 특정 사용자의 메시지만 검색 (Optional)
        room_id: 특정 채팅방에서만 검색 (Optional)
        message_type: 메시지 타입 필터 (Optional)
        start_date: 검색 시작 날짜 (Optional)
        end_date: 검색 종료 날짜 (Optional)
        limit: 결과 제한 수 (default: 20)
        skip: 건너뛸 결과 수 (default: 0)

    Returns:
        List[Message]: 검색된 메시지 목록
    """
    # -------------------------------------------------------------------------
    # Step 1: 기본 조건 설정 (삭제되지 않은 메시지만)
    # -------------------------------------------------------------------------
    conditions = [
        Message.is_deleted == False
    ]

    # -------------------------------------------------------------------------
    # Step 2: 텍스트 검색 조건 추가
    # -------------------------------------------------------------------------
    # $text: MongoDB 텍스트 인덱스를 사용한 전문 검색
    # $search: 검색할 키워드 (여러 단어는 OR 조건)
    if query:
        conditions.append({"$text": {"$search": query}})

    # -------------------------------------------------------------------------
    # Step 3: 추가 필터 조건 동적 구성 (Specification Pattern)
    # -------------------------------------------------------------------------
    if user_id:
        conditions.append(Message.user_id == user_id)

    if room_id:
        conditions.append(Message.room_id == room_id)

    if message_type:
        conditions.append(Message.message_type == message_type)

    if start_date:
        conditions.append(Message.created_at >= start_date)

    if end_date:
        conditions.append(Message.created_at <= end_date)

    # -------------------------------------------------------------------------
    # Step 4: 쿼리 필터 조합 및 실행
    # -------------------------------------------------------------------------
    # 조건이 하나면 그대로, 여러 개면 $and로 조합
    if len(conditions) == 1:
        query_filter = conditions[0]
    else:
        query_filter = {"$and": conditions}

    messages = await (
        Message.find(query_filter)
        .sort([("created_at", DESCENDING)])
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    return messages


async def get_search_results_count(
    query: str,
    user_id: Optional[int] = None,
    room_id: Optional[int] = None,
    message_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> int:
    """
    메시지 검색 결과 총 개수 조회

    [용도]
    - 검색 결과 페이지네이션
    - "총 N개의 결과" 표시

    [DRY 원칙 고려사항]
    search_messages와 조건 로직이 중복되지만,
    별도 함수로 분리하여 각 함수의 책임을 명확히 함
    (count만 필요할 때 불필요한 데이터 로드 방지)

    Args:
        (search_messages와 동일한 파라미터들)

    Returns:
        int: 검색 결과 총 개수
    """
    conditions = [
        Message.is_deleted == False
    ]

    if query:
        conditions.append({"$text": {"$search": query}})

    if user_id:
        conditions.append(Message.user_id == user_id)

    if room_id:
        conditions.append(Message.room_id == room_id)

    if message_type:
        conditions.append(Message.message_type == message_type)

    if start_date:
        conditions.append(Message.created_at >= start_date)

    if end_date:
        conditions.append(Message.created_at <= end_date)

    if len(conditions) == 1:
        query_filter = conditions[0]
    else:
        query_filter = {"$and": conditions}

    return await Message.find(query_filter).count()


# =============================================================================
# Message Statistics (메시지 통계)
# =============================================================================
#
# [용도]
# - 대시보드 통계 표시
# - 사용자 활동 분석
# - 채팅방 활성도 측정
# =============================================================================

async def get_message_stats(
    user_id: Optional[int] = None,
    room_id: Optional[int] = None
) -> Dict[str, int]:
    """
    메시지 통계 조회

    [제공 통계]
    - total_messages: 전체 메시지 수
    - today_messages: 오늘 보낸 메시지 수
    - this_week_messages: 이번 주 메시지 수

    [필터링]
    user_id 또는 room_id로 범위를 한정할 수 있음

    Args:
        user_id: 특정 사용자 통계만 조회 (Optional)
        room_id: 특정 채팅방 통계만 조회 (Optional)

    Returns:
        Dict[str, int]: 통계 정보 딕셔너리
    """
    # 시간 기준점 계산
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # 기본 조건
    conditions = [Message.is_deleted == False]

    if user_id:
        conditions.append(Message.user_id == user_id)

    if room_id:
        conditions.append(Message.room_id == room_id)

    # 각 통계 쿼리 실행
    total_messages = await Message.find(*conditions).count()

    today_conditions = conditions + [Message.created_at >= today]
    today_messages = await Message.find(*today_conditions).count()

    week_conditions = conditions + [Message.created_at >= week_ago]
    this_week_messages = await Message.find(*week_conditions).count()

    return {
        "total_messages": total_messages,
        "today_messages": today_messages,
        "this_week_messages": this_week_messages
    }


# =============================================================================
# Helper Functions (헬퍼/유틸리티 함수)
# =============================================================================
#
# [역할]
# 다른 함수들에서 공통으로 사용되거나
# 특정 목적의 조회를 수행하는 보조 함수들
# =============================================================================

async def get_latest_message_in_room(
    room_id: int,
    room_type: str = "private",
    include_deleted: bool = False
) -> Optional[Message]:
    """
    채팅방의 최신 메시지 조회

    [용도]
    - 채팅방 목록에서 마지막 메시지 미리보기
    - 채팅방 정렬 기준 (최신 활동순)

    [최적화]
    limit(1)을 사용하여 최신 하나만 조회
    인덱스: (room_id, room_type, created_at)

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입
        include_deleted: 삭제된 메시지 포함 여부

    Returns:
        Optional[Message]: 최신 메시지 또는 None (메시지 없는 경우)
    """
    conditions = [
        Message.room_id == room_id,
        Message.room_type == room_type
    ]

    if not include_deleted:
        conditions.append(Message.is_deleted == False)

    messages = await (
        Message.find(*conditions)
        .sort([("created_at", DESCENDING)])
        .limit(1)
        .to_list()
    )

    return messages[0] if messages else None


async def get_replies_to_message(message_id: str) -> List[Message]:
    """
    특정 메시지에 대한 답장들 조회

    [스레드 기능 지원]
    메시지에 달린 모든 답장을 시간순으로 조회

    Args:
        message_id: 원본 메시지 ID

    Returns:
        List[Message]: 답장 메시지 목록 (시간순 정렬)
    """
    return await (
        Message.find(
            Message.reply_to == message_id,
            Message.is_deleted == False
        )
        .sort([("created_at", 1)])  # 오래된 것부터 (시간순)
        .to_list()
    )


async def cleanup_old_deleted_messages(days_old: int = 30) -> int:
    """
    오래된 삭제 메시지 물리적 정리 (Hard Delete)

    ============================================================================
    [Soft Delete 정리 전략]
    ============================================================================

    Soft Delete된 메시지는 일정 기간 후 물리적으로 삭제합니다.
    - 복구 가능 기간: 기본 30일
    - 이후에는 스토리지 절약을 위해 완전 삭제

    [Cascade Delete]
    메시지 삭제 시 관련 데이터도 함께 삭제:
    1. MessageReadStatus: 해당 메시지의 모든 읽음 상태
    2. Message: 메시지 본체

    ============================================================================
    [성능 최적화 - Bulk Delete]
    ============================================================================

    [최적화된 방식]
    ```python
    await MessageReadStatus.find(id in message_ids).delete() # 1번
    await Message.find(id in object_ids).delete()           # 1번
    ```
    - 메시지 수와 관계없이 2번의 DB 호출

    [주의사항]
    이 함수는 배치 작업으로 실행되어야 하며,
    일반 API 요청에서는 호출하지 않아야 함 (Celery Task 등으로 스케줄링)

    Args:
        days_old: 삭제 후 경과 일수 (default: 30일)

    Returns:
        int: 삭제된 메시지 수

    Example:
        >>> # 매일 자정에 실행되는 배치 작업
        >>> deleted_count = await cleanup_old_deleted_messages(days_old=30)
        >>> logger.info(f"Cleaned up {deleted_count} old messages")
    """
    # -------------------------------------------------------------------------
    # Step 1: 삭제 대상 메시지 조회
    # -------------------------------------------------------------------------
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    # 인덱스 활용: (is_deleted, deleted_at)
    old_deleted_messages = await Message.find(
        Message.is_deleted == True,
        Message.deleted_at < cutoff_date
    ).to_list()

    if not old_deleted_messages:
        return 0

    count = len(old_deleted_messages)
    message_ids = [str(message.id) for message in old_deleted_messages]

    # -------------------------------------------------------------------------
    # Step 2: 관련 읽음 상태 벌크 삭제 (Cascade Delete)
    # -------------------------------------------------------------------------
    await MessageReadStatus.find(
        MessageReadStatus.message_id.in_(message_ids)
    ).delete()

    # -------------------------------------------------------------------------
    # Step 3: 메시지 벌크 삭제
    # -------------------------------------------------------------------------
    # ObjectId 변환 후 $in 연산자로 삭제
    from beanie import PydanticObjectId
    object_ids = [PydanticObjectId(mid) for mid in message_ids]
    await Message.find({"_id": {"$in": object_ids}}).delete()

    return count
