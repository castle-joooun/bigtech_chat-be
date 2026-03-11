"""
Domain Events Base (도메인 이벤트 베이스)
=======================================

모든 도메인 이벤트의 기본 클래스입니다.
서비스별 이벤트는 이 클래스를 상속받아 정의합니다.

사용 예시
---------
```python
from dataclasses import dataclass, field
from shared_lib.kafka import DomainEvent

@dataclass
class UserRegistered(DomainEvent):
    user_id: int = 0
    email: str = ""
    username: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.event_type = "user.registered"
```
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any
import uuid


@dataclass
class DomainEvent:
    """
    도메인 이벤트 기본 클래스

    상속 시 주의: dataclass 상속에서 필드 순서 문제를 피하려면
    하위 클래스 필드에 기본값을 제공하세요.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: str = field(default="domain.event")

    def __post_init__(self):
        """하위 클래스에서 event_type을 설정할 수 있도록 hook 제공"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """이벤트를 딕셔너리로 변환"""
        data = asdict(self)
        # datetime을 ISO 포맷 문자열로 변환
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data
