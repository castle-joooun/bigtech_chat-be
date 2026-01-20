from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, validator


class MessageBase(BaseModel):
    """메시지 기본 스키마"""
    content: str = Field(..., min_length=1, description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file, system")
    reply_to: Optional[str] = Field(None, description="답글 대상 메시지 ID")


class MessageCreate(BaseModel):
    """메시지 생성 스키마"""
    content: str = Field(..., min_length=1, max_length=5000, description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file")
    reply_to: Optional[str] = Field(None, description="답글 대상 메시지 ID")

    @validator('message_type')
    def validate_message_type(cls, v):
        allowed_types = ['text', 'image', 'file', 'system']
        if v not in allowed_types:
            raise ValueError(f'message_type must be one of {allowed_types}')
        return v


class MessageUpdate(BaseModel):
    """메시지 수정 스키마"""
    content: str = Field(..., min_length=1, max_length=5000, description="수정할 메시지 내용")


class MessageImageUpload(BaseModel):
    """이미지 메시지 생성 스키마"""
    caption: Optional[str] = Field(None, max_length=1000, description="이미지 설명")
    reply_to: Optional[str] = Field(None, description="답글 대상 메시지 ID")


class MessageReactionCreate(BaseModel):
    """메시지 반응 생성 스키마"""
    emoji: str = Field(..., min_length=1, max_length=10, description="이모지 (예: 👍, ❤️, 😂)")

    @validator('emoji')
    def validate_emoji(cls, v):
        # 기본적인 이모지 검증 (실제로는 더 복잡한 유니코드 검증이 필요)
        allowed_emojis = ['👍', '👎', '❤️', '😂', '😢', '😮', '😡', '🔥', '👏', '🎉']
        if v not in allowed_emojis:
            raise ValueError(f'emoji must be one of {allowed_emojis}')
        return v


class MessageReactionResponse(BaseModel):
    """메시지 반응 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="반응 ID")
    message_id: str = Field(..., description="메시지 ID")
    user_id: int = Field(..., description="반응한 사용자 ID")
    emoji: str = Field(..., description="이모지")
    created_at: datetime = Field(..., description="반응 생성 시간")


class MessageReadStatusResponse(BaseModel):
    """메시지 읽음 상태 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

    message_id: str = Field(..., description="메시지 ID")
    user_id: int = Field(..., description="읽은 사용자 ID")
    read_at: datetime = Field(..., description="읽은 시간")


class ReplyInfo(BaseModel):
    """답장 정보 스키마"""
    reply_to: str = Field(..., description="답장 대상 메시지 ID")
    reply_content: Optional[str] = Field(None, description="답장 대상 메시지 내용")
    reply_sender_id: Optional[int] = Field(None, description="답장 대상 메시지 작성자 ID")


class FileInfo(BaseModel):
    """파일 정보 스키마"""
    file_url: str = Field(..., description="파일 URL")
    file_name: str = Field(..., description="원본 파일명")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    file_type: str = Field(..., description="파일 MIME 타입")


class MessageResponse(BaseModel):
    """메시지 응답 스키마 (확장된 버전)"""
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

    # 동적 필드 (메시지 조회 시 추가되는 정보)
    reactions: Optional[Dict[str, Any]] = Field(None, description="반응 요약")
    read_by: Optional[List[int]] = Field(None, description="읽은 사용자 ID 목록")
    is_read: Optional[bool] = Field(None, description="현재 사용자 읽음 여부")


class MessageListResponse(BaseModel):
    """메시지 목록 응답 스키마"""
    messages: List[MessageResponse] = Field(..., description="메시지 목록")
    total_count: int = Field(..., description="전체 메시지 수")
    has_more: bool = Field(..., description="더 많은 메시지 존재 여부")


class MessageSearchRequest(BaseModel):
    """메시지 검색 요청 스키마"""
    query: str = Field(..., min_length=1, max_length=100, description="검색 키워드")
    room_id: Optional[int] = Field(None, description="특정 채팅방에서만 검색")
    message_type: Optional[str] = Field(None, description="메시지 타입 필터")
    start_date: Optional[datetime] = Field(None, description="시작 날짜")
    end_date: Optional[datetime] = Field(None, description="종료 날짜")
    limit: int = Field(default=20, ge=1, le=100, description="검색 결과 개수")
    skip: int = Field(default=0, ge=0, description="건너뛸 결과 수")


class MessageSearchResponse(BaseModel):
    """메시지 검색 응답 스키마"""
    messages: List[MessageResponse] = Field(..., description="검색된 메시지 목록")
    total_count: int = Field(..., description="전체 검색 결과 수")
    has_more: bool = Field(..., description="더 많은 결과 존재 여부")
    search_query: str = Field(..., description="검색 키워드")


class MessageDeleteRequest(BaseModel):
    """메시지 삭제 요청 스키마"""
    delete_for_everyone: bool = Field(default=False, description="모든 사용자에게서 삭제 여부")


class MessageReadRequest(BaseModel):
    """메시지 읽음 처리 요청 스키마"""
    message_ids: List[str] = Field(..., description="읽음 처리할 메시지 ID 목록")


class MessageReadResponse(BaseModel):
    """메시지 읽음 처리 응답 스키마"""
    success: bool = Field(..., description="처리 성공 여부")
    read_count: int = Field(..., description="읽음 처리된 메시지 수")
    message: str = Field(..., description="처리 결과 메시지")


class MessageStatsResponse(BaseModel):
    """메시지 통계 응답 스키마"""
    total_messages: int = Field(..., description="전체 메시지 수")
    unread_messages: int = Field(..., description="읽지 않은 메시지 수")
    today_messages: int = Field(..., description="오늘 메시지 수")
    this_week_messages: int = Field(..., description="이번 주 메시지 수")
