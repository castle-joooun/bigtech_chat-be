"""
Chat Room Schemas (채팅방 스키마)
================================

채팅방 API의 요청/응답 스키마를 정의합니다.

채팅방 타입
-----------
| 타입    | 설명                 |
|--------|---------------------|
| direct | 1:1 채팅방 (현재 구현) |
| group  | 그룹 채팅방 (향후 구현) |

채팅방 목록 정렬
----------------
- updated_at 기준 내림차순 (최근 활동순)
- 새 메시지 도착 시 updated_at 갱신

관련 파일
---------
- app/models/chat_rooms.py: SQLAlchemy 모델
- app/api/chat_room.py: API 엔드포인트
- app/services/chat_room_service.py: 비즈니스 로직
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Request Schemas (요청 스키마)
# =============================================================================

class ChatRoomCreate(BaseModel):
    """
    채팅방 생성 스키마

    POST /chat-rooms 요청 바디에 사용됩니다 (미사용).
    현재는 GET /chat-rooms/check/{participant_id}로 대체됨.

    Attributes:
        participant_id: 상대방 사용자 ID
    """
    participant_id: int = Field(..., description="상대방 사용자 ID")


# =============================================================================
# Response Schemas (응답 스키마)
# =============================================================================

class ChatRoomResponse(BaseModel):
    """
    채팅방 응답 스키마

    채팅방 정보와 관련 메타데이터를 반환합니다.

    Attributes:
        id: 채팅방 고유 ID
        user_1_id: 첫 번째 참여자 ID
        user_2_id: 두 번째 참여자 ID
        room_type: 채팅방 타입 (direct/group)
        created_at: 생성 시각
        updated_at: 마지막 활동 시각
        participants: 참여자 정보 목록
        last_message: 마지막 메시지 요약
        unread_count: 읽지 않은 메시지 수

    응답 예시:
        {
            "id": 123,
            "user_1_id": 1,
            "user_2_id": 2,
            "room_type": "direct",
            "participants": [
                {"id": 1, "username": "user1"},
                {"id": 2, "username": "user2"}
            ],
            "last_message": {"content": "안녕!", "created_at": "..."},
            "unread_count": 3
        }
    """
    model_config = ConfigDict(from_attributes=True)

    # 기본 필드 (MySQL)
    id: int = Field(..., description="채팅방 ID")
    user_1_id: int = Field(..., description="사용자 1 ID")
    user_2_id: int = Field(..., description="사용자 2 ID")
    room_type: str = Field(default="direct", description="채팅방 타입")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")

    # 추가 정보 (조합 데이터)
    participants: Optional[List[dict]] = Field(
        default=None,
        description="참여자 정보 [{id, username}, ...]"
    )
    last_message: Optional[dict] = Field(
        default=None,
        description="마지막 메시지 {content, created_at, user_id}"
    )
    unread_count: int = Field(
        default=0,
        description="읽지 않은 메시지 수"
    )
