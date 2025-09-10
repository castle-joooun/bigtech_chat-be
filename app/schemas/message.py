from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class MessageBase(BaseModel):
    """메시지 기본 스키마"""
    content: str = Field(..., min_length=1, description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file, system")
    reply_to: Optional[str] = Field(None, description="답글 대상 메시지 ID")


class MessageCreate(MessageBase):
    """메시지 생성 스키마"""
    room_id: int = Field(..., description="채팅방 ID")
    room_type: str = Field(..., description="채팅방 타입: private (1:1) or group")


class MessageUpdate(BaseModel):
    """메시지 수정 스키마"""
    content: str = Field(..., min_length=1, description="수정된 메시지 내용")


class MessageResponse(MessageBase):
    """메시지 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="메시지 ID")
    user_id: int = Field(..., description="메시지 발송자 ID")
    room_id: int = Field(..., description="채팅방 ID")
    room_type: str = Field(..., description="채팅방 타입: private or group")
    is_edited: bool = Field(..., description="수정 여부")
    edited_at: Optional[datetime] = Field(None, description="수정일시")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")


class MessageWithUser(MessageResponse):
    """사용자 정보가 포함된 메시지 스키마"""
    sender: Optional[dict] = Field(None, description="발송자 정보")
    reply_message: Optional[dict] = Field(None, description="답글 대상 메시지 정보")
    read_by: List[dict] = Field(default_factory=list, description="메시지를 읽은 사용자 목록")


class MessageList(BaseModel):
    """메시지 목록 스키마"""
    messages: List[MessageWithUser] = Field(..., description="메시지 목록")
    total: int = Field(..., description="전체 메시지 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")


class MessageSearch(BaseModel):
    """메시지 검색 스키마"""
    query: str = Field(..., min_length=1, description="검색 쿼리")
    room_id: Optional[int] = Field(None, description="특정 채팅방에서 검색")
    room_type: Optional[str] = Field(None, description="채팅방 타입으로 필터링")
    message_type: Optional[str] = Field(None, description="메시지 타입으로 필터링")
    date_from: Optional[datetime] = Field(None, description="검색 시작 날짜")
    date_to: Optional[datetime] = Field(None, description="검색 종료 날짜")
    limit: int = Field(default=50, ge=1, le=100, description="검색 결과 수")
    skip: int = Field(default=0, ge=0, description="건너뛸 항목 수")


class MessageReaction(BaseModel):
    """메시지 반응 스키마"""
    message_id: str = Field(..., description="메시지 ID")
    reaction: str = Field(..., min_length=1, max_length=10, description="반응 (이모지)")


class MessagePin(BaseModel):
    """메시지 고정 스키마"""
    message_id: str = Field(..., description="고정할 메시지 ID")
    is_pinned: bool = Field(..., description="고정 여부")


class MessageDelete(BaseModel):
    """메시지 삭제 스키마"""
    message_id: str = Field(..., description="삭제할 메시지 ID")
    delete_for_everyone: bool = Field(default=False, description="모든 사용자에게서 삭제 여부")


class MessageRead(BaseModel):
    """메시지 읽음 처리 스키마"""
    message_ids: List[str] = Field(..., description="읽음 처리할 메시지 ID 목록")
    room_id: int = Field(..., description="채팅방 ID")
