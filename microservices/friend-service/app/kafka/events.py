"""
Friend Domain Events (친구 도메인 이벤트)
========================================

친구 관계에서 발생하는 도메인 이벤트를 정의합니다.

Event-Driven Architecture
-------------------------
```
┌─────────────────┐      Kafka       ┌─────────────────┐
│ Friend Service  │ ────────────────▶│  Chat Service   │
│   (Publisher)   │ friend.events    │  (Subscriber)   │
└─────────────────┘                  └─────────────────┘
         │
         │ FriendRequestSent        채팅방 생성
         │ FriendRequestAccepted    DM 기능 활성화
         │ FriendRequestRejected
         │ FriendRequestCancelled
         ▼
┌─────────────────────────────────────────────────────┐
│                    Kafka Cluster                     │
│          topic: friend.events                        │
└─────────────────────────────────────────────────────┘
```

이벤트 흐름
-----------
1. FriendRequestSent:
   - 친구 요청 전송 시 발행
   - 대상자에게 알림 표시

2. FriendRequestAccepted:
   - 친구 요청 수락 시 발행
   - 양쪽 사용자에게 알림
   - Chat Service에서 DM 채팅방 생성

3. FriendRequestRejected:
   - 친구 요청 거절 시 발행
   - (선택적) 요청자에게 알림

4. FriendRequestCancelled:
   - 요청자가 요청 취소 시 발행
   - 대상자의 요청 목록에서 제거

이벤트 설계 원칙
----------------
1. 불변성: @dataclass로 정의
2. 자기 기술적: __event_type__ 필드
3. 타임스탬프 필수
4. 과거형 명명 (Sent, Accepted, Rejected, Cancelled)

관련 파일
---------
- app/kafka/producer.py: 이벤트 발행
- app/api/friend.py: 이벤트 생성 및 발행 호출
"""

from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class DomainEvent:
    """
    도메인 이벤트 기본 클래스

    모든 친구 도메인 이벤트의 부모 클래스.

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
class FriendRequestSent(DomainEvent):
    """
    친구 요청 전송 이벤트

    발생 시점:
        친구 요청이 성공적으로 생성된 후

    구독자 액션:
        - Notification: 대상자에게 친구 요청 알림
        - Chat Service: (선택적) 미리 채팅방 준비

    Attributes:
        friendship_id: 생성된 친구 관계 ID
        requester_id: 요청자 사용자 ID
        requester_name: 요청자 이름 (알림용)
        addressee_id: 대상자 사용자 ID
        addressee_name: 대상자 이름
        timestamp: 요청 시각

    Kafka 메시지 예시:
        {
            "friendship_id": 123,
            "requester_id": 1,
            "requester_name": "john_doe",
            "addressee_id": 2,
            "addressee_name": "jane_doe",
            "timestamp": "2024-01-15T10:30:00",
            "__event_type__": "FriendRequestSent"
        }
    """
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime


@dataclass
class FriendRequestAccepted(DomainEvent):
    """
    친구 요청 수락 이벤트

    발생 시점:
        대상자가 친구 요청을 수락한 후

    구독자 액션:
        - Notification: 양쪽 사용자에게 친구 추가 알림
        - Chat Service: DM 채팅방 자동 생성
        - User Service: 친구 수 업데이트 (선택적)

    Attributes:
        friendship_id: 친구 관계 ID
        requester_id: 요청자 ID (알림 대상)
        requester_name: 요청자 이름
        addressee_id: 수락한 사용자 ID
        addressee_name: 수락한 사용자 이름
        timestamp: 수락 시각
    """
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime


@dataclass
class FriendRequestRejected(DomainEvent):
    """
    친구 요청 거절 이벤트

    발생 시점:
        대상자가 친구 요청을 거절한 후 (soft delete)

    구독자 액션:
        - (선택적) 요청자에게 거절 알림
        - 일반적으로 무시 처리

    Attributes:
        friendship_id: 친구 관계 ID (삭제됨)
        requester_id: 요청자 ID
        addressee_id: 거절한 사용자 ID
        timestamp: 거절 시각

    참고:
        - 거절은 민감할 수 있어 알림을 보내지 않는 것이 일반적
        - 로깅/감사 목적으로 이벤트는 발행
    """
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime


@dataclass
class FriendRequestCancelled(DomainEvent):
    """
    친구 요청 취소 이벤트

    발생 시점:
        요청자가 자신이 보낸 친구 요청을 취소한 후

    구독자 액션:
        - Notification: 대상자의 요청 목록에서 제거

    Attributes:
        friendship_id: 친구 관계 ID (삭제됨)
        requester_id: 취소한 사용자 ID
        addressee_id: 대상자 ID
        timestamp: 취소 시각
    """
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime
