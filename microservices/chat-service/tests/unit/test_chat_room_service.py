"""
Unit tests for chat_room_service.py

Tests for chat room CRUD operations and helper functions.
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.chat_rooms import ChatRoom
from app.services import chat_room_service


# =============================================================================
# Find Chat Room by ID Tests
# =============================================================================

class TestFindChatRoomById:
    """Tests for find_chat_room_by_id function"""

    async def test_find_existing_room(
        self, db_session: AsyncSession, chat_room: ChatRoom
    ):
        """Should return chat room when ID exists"""
        result = await chat_room_service.find_chat_room_by_id(
            db_session, chat_room.id
        )

        assert result is not None
        assert result.id == chat_room.id

    async def test_find_nonexistent_room(self, db_session: AsyncSession):
        """Should return None when ID doesn't exist"""
        result = await chat_room_service.find_chat_room_by_id(
            db_session, 99999
        )

        assert result is None


# =============================================================================
# Find Existing Chat Room Tests
# =============================================================================

class TestFindExistingChatRoom:
    """Tests for find_existing_chat_room function"""

    async def test_find_existing_room(
        self, db_session: AsyncSession, user_1: User, user_2: User, chat_room: ChatRoom
    ):
        """Should find existing chat room between two users"""
        result = await chat_room_service.find_existing_chat_room(
            db_session, user_1.id, user_2.id
        )

        assert result is not None
        assert result.id == chat_room.id

    async def test_find_existing_room_reverse_order(
        self, db_session: AsyncSession, user_1: User, user_2: User, chat_room: ChatRoom
    ):
        """Should find room regardless of user order"""
        result = await chat_room_service.find_existing_chat_room(
            db_session, user_2.id, user_1.id
        )

        assert result is not None
        assert result.id == chat_room.id

    async def test_find_no_existing_room(
        self, db_session: AsyncSession, user_2: User, user_3: User
    ):
        """Should return None when no room exists"""
        result = await chat_room_service.find_existing_chat_room(
            db_session, user_2.id, user_3.id
        )

        assert result is None


# =============================================================================
# Create Chat Room Tests
# =============================================================================

class TestCreateChatRoom:
    """Tests for create_chat_room function"""

    async def test_create_room_success(
        self, db_session: AsyncSession, user_2: User, user_3: User
    ):
        """Should create a new chat room"""
        result = await chat_room_service.create_chat_room(
            db_session, user_2.id, user_3.id
        )

        assert result is not None
        assert result.id is not None
        assert result.created_at is not None

    async def test_create_room_orders_user_ids(
        self, db_session: AsyncSession, user_2: User, user_3: User
    ):
        """Should set smaller user_id as user_1_id"""
        result = await chat_room_service.create_chat_room(
            db_session, user_3.id, user_2.id
        )

        # user_2.id (2) < user_3.id (3), so user_2 should be user_1
        assert result.user_1_id == user_2.id
        assert result.user_2_id == user_3.id

    async def test_create_room_persists_to_database(
        self, db_session: AsyncSession, user_2: User, user_3: User
    ):
        """Should persist room to database"""
        result = await chat_room_service.create_chat_room(
            db_session, user_2.id, user_3.id
        )

        # Verify by querying
        found = await chat_room_service.find_chat_room_by_id(
            db_session, result.id
        )
        assert found is not None
        assert found.id == result.id


# =============================================================================
# Update Chat Room Timestamp Tests
# =============================================================================

class TestUpdateChatRoomTimestamp:
    """Tests for update_chat_room_timestamp function"""

    async def test_update_timestamp(
        self, db_session: AsyncSession, chat_room: ChatRoom
    ):
        """Should update updated_at timestamp"""
        original_updated_at = chat_room.updated_at

        result = await chat_room_service.update_chat_room_timestamp(
            db_session, chat_room
        )

        assert result is not None
        assert result.updated_at >= original_updated_at


# =============================================================================
# Get User Chat Rooms Tests
# =============================================================================

class TestGetUserChatRooms:
    """Tests for get_user_chat_rooms function"""

    async def test_get_rooms_for_user(
        self, db_session: AsyncSession, user_1: User, chat_room: ChatRoom, chat_room_2: ChatRoom
    ):
        """Should return all chat rooms for a user"""
        result = await chat_room_service.get_user_chat_rooms(
            db_session, user_1.id
        )

        assert len(result) == 2
        room_ids = [r.id for r in result]
        assert chat_room.id in room_ids
        assert chat_room_2.id in room_ids

    async def test_get_rooms_empty(
        self, db_session: AsyncSession, user_3: User
    ):
        """Should return empty list when user has no rooms"""
        result = await chat_room_service.get_user_chat_rooms(
            db_session, user_3.id
        )

        assert len(result) == 0

    async def test_get_rooms_with_pagination(
        self, db_session: AsyncSession, user_1: User, chat_room: ChatRoom, chat_room_2: ChatRoom
    ):
        """Should respect skip and limit parameters"""
        result = await chat_room_service.get_user_chat_rooms(
            db_session, user_1.id, skip=0, limit=1
        )

        assert len(result) == 1

    async def test_get_rooms_with_skip(
        self, db_session: AsyncSession, user_1: User, chat_room: ChatRoom, chat_room_2: ChatRoom
    ):
        """Should skip specified number of rooms"""
        result = await chat_room_service.get_user_chat_rooms(
            db_session, user_1.id, skip=1, limit=10
        )

        assert len(result) == 1

    async def test_get_rooms_ordered_by_updated_at(
        self, db_session: AsyncSession, user_1: User, chat_room: ChatRoom, chat_room_2: ChatRoom
    ):
        """Should order rooms by updated_at descending"""
        # Update chat_room_2 to be more recent
        await chat_room_service.update_chat_room_timestamp(db_session, chat_room_2)

        result = await chat_room_service.get_user_chat_rooms(
            db_session, user_1.id
        )

        assert len(result) == 2
        # Most recently updated should be first
        assert result[0].id == chat_room_2.id


# =============================================================================
# Get Other Participant ID Tests
# =============================================================================

class TestGetOtherParticipantId:
    """Tests for get_other_participant_id function"""

    def test_get_other_when_current_is_user_1(self, chat_room: ChatRoom):
        """Should return user_2_id when current user is user_1"""
        result = chat_room_service.get_other_participant_id(
            chat_room, chat_room.user_1_id
        )

        assert result == chat_room.user_2_id

    def test_get_other_when_current_is_user_2(self, chat_room: ChatRoom):
        """Should return user_1_id when current user is user_2"""
        result = chat_room_service.get_other_participant_id(
            chat_room, chat_room.user_2_id
        )

        assert result == chat_room.user_1_id


# =============================================================================
# Is User In Chat Room Tests
# =============================================================================

class TestIsUserInChatRoom:
    """Tests for is_user_in_chat_room function"""

    def test_user_1_is_in_room(self, chat_room: ChatRoom):
        """Should return True for user_1"""
        result = chat_room_service.is_user_in_chat_room(
            chat_room.user_1_id, chat_room
        )

        assert result is True

    def test_user_2_is_in_room(self, chat_room: ChatRoom):
        """Should return True for user_2"""
        result = chat_room_service.is_user_in_chat_room(
            chat_room.user_2_id, chat_room
        )

        assert result is True

    def test_other_user_not_in_room(self, chat_room: ChatRoom):
        """Should return False for user not in room"""
        result = chat_room_service.is_user_in_chat_room(
            99999, chat_room
        )

        assert result is False
