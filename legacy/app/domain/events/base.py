"""
Domain Event Base Class
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict
import json


@dataclass
class DomainEvent:
    """Domain Event 기본 클래스"""
    timestamp: datetime

    def to_dict(self) -> Dict:
        """Event를 dict로 변환"""
        data = asdict(self)
        # datetime을 ISO 형식 문자열로 변환
        data['timestamp'] = self.timestamp.isoformat()
        # Event 타입 추가 (Consumer에서 라우팅용)
        data['__event_type__'] = self.__class__.__name__
        return data

    def to_json(self) -> str:
        """Event를 JSON으로 변환"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict):
        """dict에서 Event 복원"""
        # timestamp를 datetime으로 변환
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        # __event_type__ 제거
        data.pop('__event_type__', None)
        return cls(**data)
