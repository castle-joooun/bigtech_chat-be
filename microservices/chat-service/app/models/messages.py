"""
Message Domain Models (메시지 도메인 모델)
=========================================

MongoDB에 저장되는 메시지 관련 도메인 모델입니다.
Beanie ODM을 사용하여 비동기 문서 작업을 지원합니다.

컬렉션 구조
-----------
1. messages: 채팅 메시지 저장
2. message_read_status: 읽음 상태 저장
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document
from pydantic import Field


class MessageReadStatus(Document):
    """
    메시지 읽음 상태 모델

    사용자가 메시지를 읽은 시점을 기록합니다.

    Attributes:
        message_id: 메시지 ID (ObjectId 문자열)
        user_id: 읽은 사용자 ID
        room_id: 채팅방 ID
        read_at: 읽은 시각
    """
    message_id: str = Field(..., description="메시지 ID")
    user_id: int = Field(..., description="읽은 사용자 ID")
    room_id: int = Field(..., description="채팅방 ID")
    read_at: datetime = Field(default_factory=datetime.utcnow, description="읽은 시간")

    class Settings:
        name = "message_read_status"
        indexes = [
            [("room_id", 1), ("user_id", 1), ("read_at", -1)],
            [("message_id", 1), ("user_id", 1)],
            [("user_id", 1), ("read_at", -1)],
        ]


class Message(Document):
    """
    메시지 모델 (Aggregate Root)

    1:1 채팅 메시지의 핵심 도메인 모델입니다.

    메시지 타입
    -----------
    - text: 일반 텍스트 메시지
    - image: 이미지 첨부
    - file: 파일 첨부
    - system: 시스템 메시지
    """

    user_id: int = Field(..., description="메시지를 보낸 사용자 ID")
    room_id: int = Field(..., description="메시지가 전송된 채팅방 ID")
    room_type: str = Field(default="private", description="채팅방 타입: private, group")
    content: str = Field(..., description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file, system")

    # 파일/이미지 관련 필드
    file_url: Optional[str] = Field(None, description="첨부 파일/이미지 URL")
    file_name: Optional[str] = Field(None, description="원본 파일명")
    file_size: Optional[int] = Field(None, description="파일 크기 (bytes)")
    file_type: Optional[str] = Field(None, description="파일 MIME 타입")

    # 삭제 관련 필드 (Soft Delete)
    is_deleted: bool = Field(default=False, description="삭제 여부")
    deleted_at: Optional[datetime] = Field(None, description="삭제 시간")
    deleted_by: Optional[int] = Field(None, description="삭제한 사용자 ID")

    # 수정 관련 필드
    is_edited: bool = Field(default=False, description="수정 여부")
    edited_at: Optional[datetime] = Field(None, description="수정 시간")
    original_content: Optional[str] = Field(None, description="원본 내용 (수정 이력)")

    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.utcnow, description="생성 시간")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="수정 시간")

    class Settings:
        name = "messages"
        indexes = [
            [("room_id", 1), ("created_at", -1)],
            [("user_id", 1), ("created_at", -1)],
            [("room_id", 1), ("is_deleted", 1), ("created_at", -1)],
            [("content", "text")],
            [("message_type", 1), ("created_at", -1)],
        ]

    def __repr__(self):
        return f"<Message(id={self.id}, user_id={self.user_id}, room_id={self.room_id}, type={self.message_type})>"

    async def get_read_status(self) -> List[MessageReadStatus]:
        """메시지 읽음 상태 조회"""
        return await MessageReadStatus.find(
            MessageReadStatus.message_id == str(self.id)
        ).to_list()

    async def is_read_by_user(self, user_id: int) -> bool:
        """특정 사용자가 읽었는지 확인"""
        read_status = await MessageReadStatus.find_one(
            MessageReadStatus.message_id == str(self.id),
            MessageReadStatus.user_id == user_id
        )
        return read_status is not None

    def soft_delete(self, deleted_by_user_id: int) -> None:
        """Soft Delete 처리"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_user_id
        self.updated_at = datetime.utcnow()

    def edit_content(self, new_content: str) -> None:
        """메시지 내용 수정"""
        if not self.is_edited:
            self.original_content = self.content

        self.content = new_content
        self.is_edited = True
        self.edited_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
