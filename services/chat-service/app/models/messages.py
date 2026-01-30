from datetime import datetime
from typing import Optional, List, Dict, Any
from beanie import Document
from pydantic import Field


class MessageReaction(Document):
    """메시지 이모지 반응 모델"""
    message_id: str = Field(..., description="반응 대상 메시지 ID")
    user_id: int = Field(..., description="반응한 사용자 ID")
    emoji: str = Field(..., description="이모지 (예: 👍, ❤️, 😂)")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "message_reactions"
        indexes = [
            [("message_id", 1), ("emoji", 1)],  # 메시지별 이모지 그룹핑
            [("message_id", 1), ("user_id", 1)],  # 사용자별 반응 조회
        ]


class MessageReadStatus(Document):
    """메시지 읽음 상태 모델"""
    message_id: str = Field(..., description="메시지 ID")
    user_id: int = Field(..., description="읽은 사용자 ID")
    room_id: int = Field(..., description="채팅방 ID")
    read_at: datetime = Field(default_factory=datetime.utcnow, description="읽은 시간")

    class Settings:
        name = "message_read_status"
        indexes = [
            [("room_id", 1), ("user_id", 1), ("read_at", -1)],  # 채팅방별 사용자 읽음 상태
            [("message_id", 1), ("user_id", 1)],  # 메시지별 읽음 상태 (unique)
            [("user_id", 1), ("read_at", -1)],  # 사용자별 읽음 기록
        ]


class Message(Document):
    # 기본 필드
    user_id: int = Field(..., description="메시지를 보낸 사용자 ID")
    room_id: int = Field(..., description="메시지가 전송된 채팅방 ID")
    room_type: str = Field(..., description="채팅방 타입: private (1:1) 또는 group")
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
            # 기본 인덱스
            [("room_id", 1), ("room_type", 1), ("created_at", -1)],  # 채팅방별 메시지 조회
            [("user_id", 1), ("created_at", -1)],  # 사용자별 메시지 조회
            [("room_type", 1), ("created_at", -1)],  # 채팅방 타입별 조회

            # 삭제 관련 인덱스
            [("room_id", 1), ("is_deleted", 1), ("created_at", -1)],  # 삭제되지 않은 메시지 조회

            # 답장 관련 인덱스
            [("reply_to", 1)],  # 답장 메시지 조회

            # 검색용 텍스트 인덱스
            [("content", "text"), ("reply_content", "text")],  # 텍스트 검색

            # 파일 관련 인덱스
            [("message_type", 1), ("created_at", -1)],  # 메시지 타입별 조회
        ]

    def __repr__(self):
        return f"<Message(id={self.id}, user_id={self.user_id}, room_id={self.room_id}, type={self.message_type})>"

    async def get_reactions(self) -> List[MessageReaction]:
        """메시지의 모든 반응 조회"""
        return await MessageReaction.find(MessageReaction.message_id == str(self.id)).to_list()

    async def get_reaction_summary(self) -> Dict[str, Any]:
        """메시지 반응 요약 정보"""
        reactions = await self.get_reactions()
        summary = {}

        for reaction in reactions:
            emoji = reaction.emoji
            if emoji not in summary:
                summary[emoji] = {"count": 0, "users": []}
            summary[emoji]["count"] += 1
            summary[emoji]["users"].append(reaction.user_id)

        return summary

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
