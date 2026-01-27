from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class MessageCreate(BaseModel):
    """메시지 생성 스키마"""
    content: str = Field(..., min_length=1, max_length=5000, description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file")
    reply_to: Optional[str] = Field(None, description="답글 대상 메시지 ID")

    @field_validator('message_type')
    @classmethod
    def validate_message_type(cls, v):
        allowed_types = ['text', 'image', 'file', 'system']
        if v not in allowed_types:
            raise ValueError(f'message_type must be one of {allowed_types}')
        return v


class MessageResponse(BaseModel):
    """메시지 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="메시지 ID")
    user_id: int = Field(..., description="메시지 발송자 ID")
    room_id: int = Field(..., description="채팅방 ID")
    room_type: str = Field(..., description="채팅방 타입")
    content: str = Field(..., description="메시지 내용")
    message_type: str = Field(..., description="메시지 타입")

    # 답장 관련
    reply_to: Optional[str] = Field(None, description="답글 대상 메시지 ID")
    reply_content: Optional[str] = Field(None, description="답글 대상 메시지 내용")
    reply_sender_id: Optional[int] = Field(None, description="답글 대상 메시지 작성자 ID")

    # 파일/이미지 관련
    file_url: Optional[str] = Field(None, description="첨부 파일/이미지 URL")
    file_name: Optional[str] = Field(None, description="원본 파일명")
    file_size: Optional[int] = Field(None, description="파일 크기")
    file_type: Optional[str] = Field(None, description="파일 타입")

    # 삭제 관련
    is_deleted: bool = Field(default=False, description="삭제 여부")
    deleted_at: Optional[datetime] = Field(None, description="삭제 시간")

    # 수정 관련
    is_edited: bool = Field(default=False, description="수정 여부")
    edited_at: Optional[datetime] = Field(None, description="수정 시간")

    # 시간 정보
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")

    # 동적 필드
    reactions: Optional[Dict[str, Any]] = Field(None, description="반응 요약")
    read_by: Optional[List[int]] = Field(None, description="읽은 사용자 ID 목록")
    is_read: Optional[bool] = Field(None, description="현재 사용자 읽음 여부")


class MessageListResponse(BaseModel):
    """메시지 목록 응답 스키마"""
    messages: List[MessageResponse] = Field(..., description="메시지 목록")
    total_count: int = Field(..., description="전체 메시지 수")
    has_more: bool = Field(..., description="더 많은 메시지 존재 여부")


class MessageReadRequest(BaseModel):
    """메시지 읽음 처리 요청 스키마"""
    message_ids: List[str] = Field(..., description="읽음 처리할 메시지 ID 목록")


class MessageReadResponse(BaseModel):
    """메시지 읽음 처리 응답 스키마"""
    success: bool = Field(..., description="처리 성공 여부")
    read_count: int = Field(..., description="읽음 처리된 메시지 수")
    message: str = Field(..., description="처리 결과 메시지")
