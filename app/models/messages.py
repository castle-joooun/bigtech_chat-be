from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field


class Message(Document):
    user_id: int = Field(..., description="User ID who sent the message")
    room_id: int = Field(..., description="Room ID where message was sent")
    room_type: str = Field(..., description="Type of room: private (1:1) or group")
    content: str = Field(..., description="Message content")
    message_type: str = Field(default="text", description="Type of message: text, image, file, system")
    reply_to: Optional[str] = Field(None, description="Message ID this is replying to")
    is_edited: bool = Field(default=False, description="Whether message was edited")
    edited_at: Optional[datetime] = Field(None, description="When message was last edited")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "messages"
        indexes = [
            [("room_id", 1), ("room_type", 1), ("created_at", -1)],  # For room message history by type
            [("user_id", 1), ("created_at", -1)],  # For user message history
            [("room_type", 1), ("created_at", -1)],  # For filtering by room type
        ]

    def __repr__(self):
        return f"<Message(id={self.id}, user_id={self.user_id}, room_id={self.room_id}, room_type={self.room_type})>"
