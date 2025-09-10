from datetime import datetime
from typing import Optional, List
from beanie import Document
from pymongo import DESCENDING
from pydantic import Field


class MessageSearch(Document):
    message_id: str = Field(..., description="Original message ID from messages collection")
    user_id: int = Field(..., description="User ID who sent the message")
    username: str = Field(..., description="Username for search display")
    room_id: int = Field(..., description="Room ID where message was sent")
    room_type: str = Field(..., description="Type of room: private (1:1) or group")
    room_name: Optional[str] = Field(None, description="Room name for group chats")
    
    # Search optimized content fields
    content: str = Field(..., description="Original message content")
    content_normalized: str = Field(..., description="Normalized content for better search")
    content_keywords: List[str] = Field(default_factory=list, description="Extracted keywords for search")
    
    # Message metadata
    message_type: str = Field(default="text", description="Type of message: text, image, file, system")
    language: Optional[str] = Field(None, description="Detected language of the message")
    
    # Search relevance fields
    search_priority: int = Field(default=1, description="Search priority (1-10, higher = more important)")
    is_searchable: bool = Field(default=True, description="Whether message should appear in search results")
    
    # Participant information for permission checking
    participants: List[int] = Field(default_factory=list, description="User IDs who can see this message")
    
    # Timestamps
    message_created_at: datetime = Field(..., description="When the original message was created")
    indexed_at: datetime = Field(default_factory=datetime.utcnow, description="When this search record was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When this search record was last updated")

    class Settings:
        name = "message_search"
        indexes = [
            # Full-text search indexes
            [("content", "text"), ("content_keywords", "text"), ("username", "text")],
            
            # Room-based search
            [("room_id", 1), ("room_type", 1), ("message_created_at", -1)],
            
            # User-based search
            [("user_id", 1), ("message_created_at", -1)],
            
            # Permission-based search (for private messages)
            [("participants", 1), ("is_searchable", 1), ("message_created_at", -1)],
            
            # Priority and type filtering
            [("message_type", 1), ("search_priority", -1), ("message_created_at", -1)],
            
            # Language-based search
            [("language", 1), ("message_created_at", -1)],
            
            # Composite search optimization
            [("room_type", 1), ("is_searchable", 1), ("search_priority", -1), ("message_created_at", -1)],
        ]

    def __repr__(self):
        return f"<MessageSearch(message_id={self.message_id}, user_id={self.user_id}, room_id={self.room_id})>"

    @classmethod
    async def create_from_message(cls, message, username: str, room_name: Optional[str] = None, participants: List[int] = None):
        """
        Create a search index entry from a Message document
        """
        import re
        
        # Normalize content for better search
        content_normalized = message.content.lower().strip()
        
        # Extract keywords (simple implementation - can be enhanced with NLP)
        keywords = re.findall(r'\b\w{3,}\b', content_normalized)
        keywords = list(set(keywords))  # Remove duplicates
        
        # Determine search priority based on message type
        priority_map = {
            "text": 5,
            "image": 3,
            "file": 4,
            "system": 1
        }
        
        search_doc = cls(
            message_id=str(message.id),
            user_id=message.user_id,
            username=username,
            room_id=message.room_id,
            room_type=message.room_type,
            room_name=room_name,
            content=message.content,
            content_normalized=content_normalized,
            content_keywords=keywords,
            message_type=message.message_type,
            search_priority=priority_map.get(message.message_type, 1),
            is_searchable=message.message_type != "system",  # System messages might not be searchable
            participants=participants or [],
            message_created_at=message.created_at,
        )
        
        return await search_doc.save()

    @classmethod
    async def search_messages(
        cls,
        query: str,
        user_id: int,
        room_id: Optional[int] = None,
        room_type: Optional[str] = None,
        message_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ):
        """
        Search messages with various filters
        """
        search_filter = {
            "is_searchable": True,
            "$or": [
                {"participants": user_id},  # User is a participant
                {"room_type": "group", "is_searchable": True}  # Public group messages
            ]
        }
        
        if room_id:
            search_filter["room_id"] = room_id
            
        if room_type:
            search_filter["room_type"] = room_type
            
        if message_type:
            search_filter["message_type"] = message_type
        
        # Full-text search
        if query:
            search_filter["$text"] = {"$search": query}
            
        return await cls.find(
            search_filter
        ).sort([
            ("search_priority", DESCENDING),
            ("message_created_at", DESCENDING)
        ]).skip(skip).limit(limit).to_list()

    async def update_search_data(self, **kwargs):
        """
        Update search-specific fields
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.updated_at = datetime.utcnow()
        return await self.save()