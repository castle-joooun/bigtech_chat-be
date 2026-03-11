"""
User Domain Events (사용자 도메인 이벤트)
========================================

도메인 주도 설계(DDD)의 도메인 이벤트를 정의합니다.

Domain Event란?
---------------
도메인에서 발생한 중요한 사건(fact)을 나타내는 객체.
과거형으로 명명 (UserRegistered, ProfileUpdated)

```
                      Kafka
User Service ─────────────────────▶ Friend Service
(Publisher)       user.events       (Subscriber)
                      │
                      │ UserRegistered
                      │ UserOnlineStatusChanged
                      │
                      ▼
              ┌──────────────┐
              │ Chat Service │
              │ (Subscriber) │
              └──────────────┘
```

Event Sourcing과의 관계
-----------------------
- Event Sourcing: 모든 상태 변경을 이벤트로 저장
- 이 프로젝트: 이벤트 발행만 (순수 Event Sourcing 아님)
- 다른 서비스가 구독하여 상태 동기화

이벤트 설계 원칙
----------------
1. 불변성 (Immutable):
   - @dataclass로 정의
   - 생성 후 변경 불가

2. 자기 기술적 (Self-Descriptive):
   - __event_type__ 필드로 이벤트 타입 명시
   - 소비자가 이벤트 타입별로 처리 가능

3. 타임스탬프 필수:
   - 이벤트 발생 시각 기록
   - 순서 보장 및 디버깅에 활용

4. 과거형 명명:
   - UserRegistered (O) vs UserRegister (X)
   - 이미 발생한 사실을 나타냄

이벤트 목록
-----------
| 이벤트                  | 발생 시점        | 소비자          |
|------------------------|-----------------|-----------------|
| UserRegistered         | 회원가입 완료    | Friend, Chat    |
| UserProfileUpdated     | 프로필 수정      | Chat            |
| UserOnlineStatusChanged| 로그인/로그아웃  | Friend, Chat    |

직렬화
------
to_dict() 메서드로 JSON 직렬화 가능.
Kafka Producer에서 사용.

SOLID 원칙
----------
- OCP: 새 이벤트 추가 시 DomainEvent 상속만 하면 됨
- LSP: 모든 이벤트는 DomainEvent로 대체 가능

사용 예시
---------
```python
from app.kafka.events import UserRegistered
from datetime import datetime

event = UserRegistered(
    user_id=123,
    email="test@example.com",
    username="testuser",
    display_name="Test User",
    timestamp=datetime.utcnow()
)

# Kafka 발행용 dict 변환
event_dict = event.to_dict()
# {
#     "user_id": 123,
#     "email": "test@example.com",
#     "username": "testuser",
#     "display_name": "Test User",
#     "timestamp": "2024-01-15T10:30:00",
#     "__event_type__": "UserRegistered"
# }
```

관련 파일
---------
- app/kafka/producer.py: 이벤트 발행
- app/api/auth.py: 이벤트 생성 및 발행 호출
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class DomainEvent:
    """
    도메인 이벤트 기본 클래스

    모든 도메인 이벤트의 부모 클래스.
    공통 필드와 직렬화 로직 제공.

    Design Pattern: Template Method
        - to_dict()가 기본 직렬화 로직 제공
        - 하위 클래스에서 필드만 추가하면 자동 직렬화

    Attributes:
        timestamp: 이벤트 발생 시각 (UTC)

    직렬화 형식:
        - datetime → ISO 8601 문자열
        - __event_type__ 필드 자동 추가
    """
    timestamp: datetime

    def to_dict(self) -> dict:
        """
        이벤트를 딕셔너리로 직렬화

        Kafka Producer의 value_serializer에서 사용.
        JSON 직렬화 가능한 형태로 변환.

        Returns:
            dict: 직렬화된 이벤트 데이터

        변환 규칙:
            - datetime → ISO 8601 문자열 (예: "2024-01-15T10:30:00")
            - __event_type__ 필드 추가 (클래스명)
        """
        data = asdict(self)
        # datetime을 ISO 형식 문자열로 변환
        data['timestamp'] = self.timestamp.isoformat()
        # 이벤트 타입 명시 (소비자가 타입별로 처리 가능)
        data['__event_type__'] = self.__class__.__name__
        return data


@dataclass
class UserRegistered(DomainEvent):
    """
    사용자 등록 이벤트

    발생 시점:
        회원가입 완료 후 (auth.py의 register 엔드포인트)

    구독자:
        - Friend Service: 신규 사용자 친구 추천
        - Chat Service: 사용자 정보 캐싱

    Kafka 토픽:
        user.events

    Attributes:
        user_id: 생성된 사용자 ID
        email: 이메일 주소
        username: 사용자명
        display_name: 표시 이름
        timestamp: 등록 시각

    사용 예시:
        event = UserRegistered(
            user_id=123,
            email="test@example.com",
            username="testuser",
            display_name="Test User",
            timestamp=datetime.utcnow()
        )
    """
    user_id: int
    email: str
    username: str
    display_name: str
    timestamp: datetime


@dataclass
class UserProfileUpdated(DomainEvent):
    """
    사용자 프로필 업데이트 이벤트

    발생 시점:
        프로필 수정 완료 후 (profile.py의 update_my_profile)

    구독자:
        - Chat Service: 채팅방 멤버 정보 업데이트

    Kafka 토픽:
        user.profile_updated

    Attributes:
        user_id: 사용자 ID
        display_name: 변경된 표시 이름
        status_message: 변경된 상태 메시지 (None 가능)
        timestamp: 업데이트 시각

    부분 업데이트:
        - None 값은 해당 필드가 변경되지 않았음을 의미
        - 소비자는 None이 아닌 필드만 업데이트
    """
    user_id: int
    display_name: str
    status_message: Optional[str]
    timestamp: datetime


@dataclass
class UserOnlineStatusChanged(DomainEvent):
    """
    온라인 상태 변경 이벤트

    발생 시점:
        - 로그인 시: is_online=True
        - 로그아웃 시: is_online=False
        - TTL 만료 시: (별도 모니터링 필요)

    구독자:
        - Friend Service: 친구에게 온라인 상태 알림
        - Chat Service: 채팅방 멤버 상태 표시

    Kafka 토픽:
        user.online_status

    Attributes:
        user_id: 사용자 ID
        is_online: 온라인 상태 (True/False)
        timestamp: 상태 변경 시각

    실시간 알림 흐름:
        1. 사용자 로그인
        2. UserOnlineStatusChanged(is_online=True) 발행
        3. Friend Service가 구독
        4. 친구 목록 조회
        5. SSE로 친구들에게 알림

    사용 예시:
        # 로그인 시
        event = UserOnlineStatusChanged(
            user_id=123,
            is_online=True,
            timestamp=datetime.utcnow()
        )

        # 로그아웃 시
        event = UserOnlineStatusChanged(
            user_id=123,
            is_online=False,
            timestamp=datetime.utcnow()
        )
    """
    user_id: int
    is_online: bool
    timestamp: datetime
