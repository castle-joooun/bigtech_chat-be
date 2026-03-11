"""
메시지 모델 (Message Models)

채팅 메시지를 저장하는 Beanie ODM 모델입니다.
MongoDB 컬렉션과 매핑되며, 1:1 채팅 데이터에 최적화되어 있습니다.

컬렉션 구조:
    ├── messages: 채팅 메시지 (핵심 데이터)
    └── message_read_status: 읽음 상태

인덱스 전략
-----------
- Compound Index: (room_id, created_at) - 채팅방별 메시지 조회
- Single Index: (user_id, created_at) - 사용자별 메시지 조회
- Text Index: (content, reply_content) - 전문 검색

소프트 삭제
-----------
메시지는 물리적으로 삭제되지 않고 is_deleted 플래그로 표시됩니다.
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document
from pydantic import Field


class MessageReadStatus(Document):
    """
    메시지 읽음 상태 모델

    사용자가 어떤 메시지를 읽었는지 추적합니다.

    Attributes:
        message_id: 읽은 메시지의 MongoDB ObjectId
        user_id: 읽은 사용자 ID
        room_id: 채팅방 ID
        read_at: 읽은 시간
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
            [("message_id", 1)],
        ]


class Message(Document):
    """
    메시지 모델 (핵심 채팅 데이터)

    1:1 채팅방에서 주고받는 메시지를 저장합니다.

    Attributes:
        user_id: 발신자 사용자 ID
        room_id: 채팅방 ID
        content: 메시지 내용
        message_type: 메시지 타입 ("text", "image", "file", "system")

        reply_to: 답장 대상 메시지 ID (Optional)
        reply_content: 답장 대상 메시지 미리보기 (Optional)
        reply_sender_id: 답장 대상 메시지 작성자 ID (Optional)

        file_url: 첨부 파일 URL (Optional)
        file_name: 원본 파일명 (Optional)
        file_size: 파일 크기 bytes (Optional)
        file_type: MIME 타입 (Optional)

        is_deleted: 소프트 삭제 여부
        is_edited: 수정 여부
    """
    user_id: int = Field(..., description="메시지를 보낸 사용자 ID")
    room_id: int = Field(..., description="메시지가 전송된 채팅방 ID")
    content: str = Field(..., description="메시지 내용")
    message_type: str = Field(default="text", description="메시지 타입: text, image, file, system")

    # 답장 관련
    reply_to: Optional[str] = Field(None, description="답장 대상 메시지 ID")
    reply_content: Optional[str] = Field(None, description="답장 대상 메시지 내용 (미리보기용)")
    reply_sender_id: Optional[int] = Field(None, description="답장 대상 메시지 작성자 ID")

    # 파일/이미지 관련
    file_url: Optional[str] = Field(None, description="첨부 파일/이미지 URL")
    file_name: Optional[str] = Field(None, description="원본 파일명")
    file_size: Optional[int] = Field(None, description="파일 크기 (bytes)")
    file_type: Optional[str] = Field(None, description="파일 MIME 타입")

    # 삭제 관련 (소프트 삭제)
    is_deleted: bool = Field(default=False, description="삭제 여부")
    deleted_at: Optional[datetime] = Field(None, description="삭제 시간")
    deleted_by: Optional[int] = Field(None, description="삭제한 사용자 ID")

    # 수정 관련
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
            [("is_deleted", 1), ("deleted_at", 1)],
            [("room_id", 1), ("is_deleted", 1), ("user_id", 1)],
            [("reply_to", 1)],
            [("content", "text"), ("reply_content", "text")],
            [("message_type", 1), ("created_at", -1)],
        ]

    def __repr__(self):
        return f"<Message(id={self.id}, user_id={self.user_id}, room_id={self.room_id}, type={self.message_type})>"

    async def get_read_status(self) -> List[MessageReadStatus]:
        """메시지 읽음 상태 조회"""
        return await MessageReadStatus.find(MessageReadStatus.message_id == str(self.id)).to_list()

    async def is_read_by_user(self, user_id: int) -> bool:
        """특정 사용자가 읽었는지 확인"""
        read_status = await MessageReadStatus.find_one(
            MessageReadStatus.message_id == str(self.id),
            MessageReadStatus.user_id == user_id
        )
        return read_status is not None

    def soft_delete(self, deleted_by_user_id: int) -> None:
        """소프트 삭제 처리"""
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
