"""
Message Schemas (메시지 스키마)
==============================

메시지 API의 요청/응답 스키마를 정의합니다.

스키마 구조
-----------
```
┌─────────────────────────────────────────────────────────────┐
│                     Request Schemas                          │
├─────────────────────────────────────────────────────────────┤
│  MessageCreate     → POST /messages/{room_id}               │
│  MessageReadRequest → POST /messages/read                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Response Schemas                         │
├─────────────────────────────────────────────────────────────┤
│  MessageResponse     → 메시지 상세 정보                      │
│  MessageListResponse → 메시지 목록 + 페이지네이션             │
│  MessageReadResponse → 읽음 처리 결과                        │
└─────────────────────────────────────────────────────────────┘
```

메시지 타입
-----------
| 타입    | 설명                              |
|--------|----------------------------------|
| text   | 일반 텍스트 메시지                  |
| image  | 이미지 첨부                        |
| file   | 파일 첨부                          |
| system | 시스템 메시지 (입장, 퇴장 알림)       |

메시지 ID 형식
--------------
MongoDB ObjectId를 문자열로 변환하여 사용:
예: "507f1f77bcf86cd799439011"

관련 파일
---------
- app/models/messages.py: Beanie Document 모델
- app/api/message.py: API 엔드포인트
- app/services/message_service.py: 비즈니스 로직
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


# =============================================================================
# Request Schemas (요청 스키마)
# =============================================================================

class MessageCreate(BaseModel):
    """
    메시지 생성 스키마

    POST /messages/{room_id} 요청 바디에 사용됩니다.

    Attributes:
        content: 메시지 내용 (1-300자)
        message_type: 메시지 타입 (기본: text)

    사용 예시:
        POST /messages/123
        {
            "content": "안녕하세요!",
            "message_type": "text"
        }
    """
    content: str = Field(..., min_length=1, max_length=300, description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file")

    @field_validator('message_type')
    @classmethod
    def validate_message_type(cls, v):
        """메시지 타입 검증"""
        allowed_types = ['text', 'image', 'file', 'system']
        if v not in allowed_types:
            raise ValueError(f'message_type must be one of {allowed_types}')
        return v


# =============================================================================
# Response Schemas (응답 스키마)
# =============================================================================

class MessageResponse(BaseModel):
    """
    메시지 응답 스키마

    메시지의 전체 정보를 반환합니다.

    필드 분류:
        - 기본 필드: id, user_id, room_id, content, message_type
        - 파일 관련: file_url, file_name, file_size, file_type
        - 상태 관련: is_deleted, is_edited
        - 시간 정보: created_at, updated_at
        - 동적 필드: reactions, read_by, is_read

    응답 예시:
        {
            "id": "507f1f77bcf86cd799439011",
            "user_id": 1,
            "room_id": 123,
            "content": "안녕하세요!",
            "message_type": "text",
            "created_at": "2024-01-01T12:00:00Z",
            ...
        }
    """
    model_config = ConfigDict(from_attributes=True)

    # 기본 필드
    id: str = Field(..., description="메시지 ID (MongoDB ObjectId)")
    user_id: int = Field(..., description="메시지 발송자 ID")
    room_id: int = Field(..., description="채팅방 ID")
    room_type: str = Field(..., description="채팅방 타입")
    content: str = Field(..., description="메시지 내용")
    message_type: str = Field(..., description="메시지 타입")

    # 파일/이미지 관련 필드
    file_url: Optional[str] = Field(None, description="첨부 파일/이미지 URL")
    file_name: Optional[str] = Field(None, description="원본 파일명")
    file_size: Optional[int] = Field(None, description="파일 크기 (바이트)")
    file_type: Optional[str] = Field(None, description="파일 MIME 타입")

    # 삭제 관련 필드 (Soft Delete)
    is_deleted: bool = Field(default=False, description="삭제 여부")
    deleted_at: Optional[datetime] = Field(None, description="삭제 시간")

    # 수정 관련 필드
    is_edited: bool = Field(default=False, description="수정 여부")
    edited_at: Optional[datetime] = Field(None, description="수정 시간")

    # 시간 정보
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")

    # 동적 필드 (선택적으로 포함)
    read_by: Optional[List[int]] = Field(None, description="읽은 사용자 ID 목록")
    is_read: Optional[bool] = Field(None, description="현재 사용자 읽음 여부")


class MessageListResponse(BaseModel):
    """
    메시지 목록 응답 스키마

    GET /messages/{room_id} 응답에 사용됩니다.
    페이지네이션 정보를 포함합니다.

    Attributes:
        messages: 메시지 목록 (오래된 순)
        total_count: 채팅방의 전체 메시지 수
        has_more: 더 로드할 메시지 존재 여부

    클라이언트 사용:
        if (response.has_more) {
            loadMoreMessages(skip + limit);
        }
    """
    messages: List[MessageResponse] = Field(..., description="메시지 목록")
    total_count: int = Field(..., description="전체 메시지 수")
    has_more: bool = Field(..., description="더 많은 메시지 존재 여부")


class MessageUpdateRequest(BaseModel):
    """
    메시지 수정 요청 스키마

    PUT /messages/{message_id} 요청 바디에 사용됩니다.

    Attributes:
        content: 수정할 메시지 내용 (1-300자)

    사용 예시:
        PUT /messages/507f1f77bcf86cd799439011
        {
            "content": "수정된 메시지입니다"
        }
    """
    content: str = Field(..., min_length=1, max_length=300, description="수정할 메시지 내용")


class MessageReadRequest(BaseModel):
    """
    메시지 읽음 처리 요청 스키마

    POST /messages/read 요청 바디에 사용됩니다.

    Attributes:
        room_id: 채팅방 ID (명시적으로 전달하여 DB 조회 최소화)
        message_ids: 읽음 처리할 메시지 ID 목록

    사용 예시:
        POST /messages/read
        {
            "room_id": 123,
            "message_ids": ["507f1f77...", "507f1f78..."]
        }

    주의:
        모든 메시지가 같은 채팅방에 속해야 합니다.
    """
    room_id: int = Field(..., description="채팅방 ID")
    message_ids: List[str] = Field(..., description="읽음 처리할 메시지 ID 목록")


class MessageReadResponse(BaseModel):
    """
    메시지 읽음 처리 응답 스키마

    Attributes:
        success: 처리 성공 여부
        read_count: 실제 읽음 처리된 메시지 수
        message: 결과 메시지

    참고:
        이미 읽은 메시지는 read_count에 포함되지 않습니다.
    """
    success: bool = Field(..., description="처리 성공 여부")
    read_count: int = Field(..., description="읽음 처리된 메시지 수")
    message: str = Field(..., description="처리 결과 메시지")
