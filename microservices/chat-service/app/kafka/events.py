"""
Chat/Message Domain Events (채팅/메시지 도메인 이벤트)
=====================================================

채팅과 메시지에서 발생하는 도메인 이벤트를 정의합니다.

Event-Driven Architecture
-------------------------
```
┌─────────────────┐      Kafka       ┌─────────────────┐
│  Chat Service   │ ────────────────▶│  User Service   │
│   (Publisher)   │ message.events   │  (Subscriber)   │
└─────────────────┘                  └─────────────────┘
         │
         │ MessageSent         알림 전송
         │ MessagesRead        읽음 상태 동기화
         │ MessageDeleted
         │ ChatRoomCreated
         ▼
┌─────────────────────────────────────────────────────┐
│                    Kafka Cluster                     │
│          topic: message.events                       │
└─────────────────────────────────────────────────────┘
```

실시간 메시지 스트리밍
----------------------
```
1. 메시지 전송
   POST /messages/{room_id}
         │
         ▼
2. Kafka 발행
   MessageSent 이벤트
         │
         ▼
3. SSE 스트림
   GET /messages/stream/{room_id}
         │
         ▼
4. 클라이언트
   EventSource → 실시간 수신
```

이벤트 목록
-----------
1. MessageSent:
   - 새 메시지 전송 시 발행
   - 실시간 채팅 스트리밍의 핵심

2. MessagesRead:
   - 메시지 읽음 처리 시 발행
   - 읽음 표시 UI 업데이트

3. MessageDeleted:
   - 메시지 삭제 시 발행
   - 다른 사용자 화면에서 제거

4. ChatRoomCreated:
   - 채팅방 생성 시 발행
   - 참여자에게 알림

파티션 키 전략
--------------
- key=room_id: 같은 채팅방 메시지는 같은 파티션
- 순서 보장: 채팅방 내 메시지 순서 유지

관련 파일
---------
- app/kafka/producer.py: 이벤트 발행
- app/api/message.py: 이벤트 생성 및 SSE 스트림
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List


@dataclass
class DomainEvent:
    """
    도메인 이벤트 기본 클래스

    모든 채팅/메시지 도메인 이벤트의 부모 클래스.

    Attributes:
        timestamp: 이벤트 발생 시각 (UTC)

    직렬화:
        to_dict()로 JSON 직렬화 가능한 형태로 변환
    """
    timestamp: datetime

    def to_dict(self) -> dict:
        """
        이벤트를 딕셔너리로 직렬화

        Returns:
            dict: 직렬화된 이벤트 데이터
                - timestamp: ISO 8601 문자열
                - __event_type__: 클래스명
        """
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['__event_type__'] = self.__class__.__name__
        return data


@dataclass
class MessageSent(DomainEvent):
    """
    메시지 전송 이벤트

    발생 시점:
        새 메시지가 MongoDB에 저장된 직후

    구독자 액션:
        - SSE 스트림: 실시간 메시지 브로드캐스트
        - Notification: 푸시 알림 전송
        - User Service: 안 읽은 메시지 수 업데이트

    Attributes:
        message_id: 생성된 메시지 ID (MongoDB ObjectId)
        room_id: 채팅방 ID
        user_id: 메시지 작성자 ID
        username: 메시지 작성자 이름 (UI 표시용)
        content: 메시지 내용
        message_type: 메시지 타입 ("text", "image", "file")
        timestamp: 전송 시각

    Kafka 파티션:
        key=room_id → 같은 채팅방 메시지는 같은 파티션
        → 채팅방 내 메시지 순서 보장

    SSE 이벤트 형식:
        event: new_message
        data: {"id": "...", "content": "...", ...}

    사용 예시:
        await producer.publish(
            topic="message.events",
            event=MessageSent(
                message_id="507f1f77bcf86cd799439011",
                room_id=100,
                user_id=1,
                username="john_doe",
                content="안녕하세요!",
                message_type="text",
                timestamp=datetime.utcnow()
            ),
            key=str(100)  # room_id를 파티션 키로
        )
    """
    message_id: str
    room_id: int
    user_id: int
    username: str
    content: str
    message_type: str  # "text", "image", "file"
    timestamp: datetime


@dataclass
class MessagesRead(DomainEvent):
    """
    메시지 읽음 이벤트

    발생 시점:
        사용자가 메시지를 읽음 처리한 후

    구독자 액션:
        - 읽음 표시 UI 업데이트 (체크 마크)
        - 안 읽은 메시지 카운트 업데이트

    Attributes:
        room_id: 채팅방 ID
        user_id: 읽은 사용자 ID
        message_ids: 읽은 메시지 ID 목록
        timestamp: 읽은 시각

    읽음 처리 시나리오:
        1. 채팅방 진입: 모든 안 읽은 메시지 읽음 처리
        2. 스크롤: 화면에 보이는 메시지 읽음 처리
        3. 알림 클릭: 해당 메시지 읽음 처리
    """
    room_id: int
    user_id: int
    message_ids: List[str]
    timestamp: datetime


@dataclass
class MessageDeleted(DomainEvent):
    """
    메시지 삭제 이벤트

    발생 시점:
        메시지가 Soft Delete 처리된 후

    구독자 액션:
        - 다른 사용자 화면에서 메시지 제거/숨김
        - "삭제된 메시지입니다" 표시

    Attributes:
        message_id: 삭제된 메시지 ID
        room_id: 채팅방 ID
        deleted_by: 삭제한 사용자 ID
        timestamp: 삭제 시각

    삭제 정책:
        - 자신의 메시지만 삭제 가능
        - 방장은 모든 메시지 삭제 가능 (선택적)
    """
    message_id: str
    room_id: int
    deleted_by: int
    timestamp: datetime


@dataclass
class ChatRoomCreated(DomainEvent):
    """
    채팅방 생성 이벤트

    발생 시점:
        새 채팅방이 MySQL에 저장된 직후

    구독자 액션:
        - 참여자에게 알림
        - 채팅방 목록 업데이트

    Attributes:
        room_id: 생성된 채팅방 ID
        room_type: 채팅방 타입 ("direct", "group")
        creator_id: 생성자 ID
        participant_ids: 참여자 ID 목록
        timestamp: 생성 시각

    채팅방 타입:
        - direct: 1:1 채팅 (친구 간)
        - group: 그룹 채팅 (여러 명)

    사용 예시:
        await producer.publish(
            topic="message.events",
            event=ChatRoomCreated(
                room_id=100,
                room_type="direct",
                creator_id=1,
                participant_ids=[1, 2],
                timestamp=datetime.utcnow()
            ),
            key=str(100)
        )
    """
    room_id: int
    room_type: str  # "direct", "group"
    creator_id: int
    participant_ids: List[int]
    timestamp: datetime
