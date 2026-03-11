"""
Unit tests for message_service.py

Tests for message CRUD operations and read status management.
Note: MongoDB (Beanie) operations are mocked since we use SQLite for testing.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from app.services import message_service


# =============================================================================
# Create Message Tests
# =============================================================================

class TestCreateMessage:
    """Tests for create_message function"""

    @patch('app.services.message_service.Message')
    async def test_create_message_success(
        self, mock_message_class
    ):
        """Should create a new message"""
        mock_message = MagicMock()
        mock_message.insert = AsyncMock()
        mock_message_class.return_value = mock_message

        result = await message_service.create_message(
            user_id=1,
            room_id=1,
            room_type="private",
            content="Hello, World!",
            message_type="text"
        )

        mock_message.insert.assert_called_once()
        assert result == mock_message


# =============================================================================
# Find Message by ID Tests
# =============================================================================

class TestFindMessageById:
    """Tests for find_message_by_id function"""

    @patch('app.services.message_service.Message')
    @patch('app.services.message_service.PydanticObjectId')
    async def test_find_existing_message(self, mock_object_id, mock_message):
        """Should return message when ID exists"""
        expected_message = MagicMock()
        mock_message.get = AsyncMock(return_value=expected_message)

        result = await message_service.find_message_by_id(
            "507f1f77bcf86cd799439011"
        )

        assert result == expected_message

    @patch('app.services.message_service.Message')
    @patch('app.services.message_service.PydanticObjectId')
    async def test_find_nonexistent_message(self, mock_object_id, mock_message):
        """Should return None when ID doesn't exist"""
        mock_message.get = AsyncMock(return_value=None)

        result = await message_service.find_message_by_id(
            "507f1f77bcf86cd799439011"
        )

        assert result is None

    @patch('app.services.message_service.PydanticObjectId')
    async def test_find_invalid_id_returns_none(self, mock_object_id):
        """Should return None for invalid ObjectId"""
        mock_object_id.side_effect = Exception("Invalid ObjectId")

        result = await message_service.find_message_by_id("invalid_id")

        assert result is None


# =============================================================================
# Get Room Messages Tests
# =============================================================================

class TestGetRoomMessages:
    """Tests for get_room_messages function"""

    @patch('app.services.message_service.Message')
    async def test_get_messages_success(self, mock_message):
        """Should return messages for room"""
        mock_messages = [MagicMock(), MagicMock(), MagicMock()]

        # Setup the chain of method calls
        mock_find = MagicMock()
        mock_sort = MagicMock()
        mock_skip = MagicMock()
        mock_limit = MagicMock()

        mock_message.find.return_value = mock_find
        mock_find.sort.return_value = mock_sort
        mock_sort.skip.return_value = mock_skip
        mock_skip.limit.return_value = mock_limit
        mock_limit.to_list = AsyncMock(return_value=mock_messages)

        result = await message_service.get_room_messages(
            room_id=1,
            room_type="private",
            limit=50,
            skip=0
        )

        # Result should be reversed (oldest first)
        assert len(result) == 3
        mock_message.find.assert_called_once()

    @patch('app.services.message_service.Message')
    async def test_get_messages_empty(self, mock_message):
        """Should return empty list when no messages"""
        mock_find = MagicMock()
        mock_sort = MagicMock()
        mock_skip = MagicMock()
        mock_limit = MagicMock()

        mock_message.find.return_value = mock_find
        mock_find.sort.return_value = mock_sort
        mock_sort.skip.return_value = mock_skip
        mock_skip.limit.return_value = mock_limit
        mock_limit.to_list = AsyncMock(return_value=[])

        result = await message_service.get_room_messages(
            room_id=1
        )

        assert len(result) == 0


# =============================================================================
# Get Room Messages Count Tests
# =============================================================================

class TestGetRoomMessagesCount:
    """Tests for get_room_messages_count function"""

    @patch('app.services.message_service.Message')
    async def test_get_count_success(self, mock_message):
        """Should return message count"""
        mock_find = MagicMock()
        mock_message.find.return_value = mock_find
        mock_find.count = AsyncMock(return_value=10)

        result = await message_service.get_room_messages_count(
            room_id=1
        )

        assert result == 10

    @patch('app.services.message_service.Message')
    async def test_get_count_zero(self, mock_message):
        """Should return 0 when no messages"""
        mock_find = MagicMock()
        mock_message.find.return_value = mock_find
        mock_find.count = AsyncMock(return_value=0)

        result = await message_service.get_room_messages_count(
            room_id=1
        )

        assert result == 0


# =============================================================================
# Mark Message as Read Tests
# =============================================================================

class TestMarkMessageAsRead:
    """Tests for mark_message_as_read function"""

    @patch('app.services.message_service.MessageReadStatus')
    async def test_mark_as_read_new(self, mock_read_status_class):
        """Should create new read status when not exists"""
        mock_read_status_class.find_one = AsyncMock(return_value=None)

        mock_read_status = MagicMock()
        mock_read_status.insert = AsyncMock()
        mock_read_status_class.return_value = mock_read_status

        result = await message_service.mark_message_as_read(
            message_id="507f1f77bcf86cd799439011",
            user_id=1,
            room_id=1
        )

        mock_read_status.insert.assert_called_once()

    @patch('app.services.message_service.MessageReadStatus')
    async def test_mark_as_read_already_exists(self, mock_read_status_class):
        """Should return existing read status if already read"""
        existing_status = MagicMock()
        mock_read_status_class.find_one = AsyncMock(return_value=existing_status)

        result = await message_service.mark_message_as_read(
            message_id="507f1f77bcf86cd799439011",
            user_id=1,
            room_id=1
        )

        assert result == existing_status


# =============================================================================
# Mark Multiple Messages as Read Tests
# =============================================================================

class TestMarkMultipleMessagesAsRead:
    """Tests for mark_multiple_messages_as_read function"""

    @patch('app.services.message_service.MessageReadStatus')
    async def test_mark_multiple_success(self, mock_read_status_class):
        """Should mark all unread messages as read"""
        mock_read_status_class.find_one = AsyncMock(return_value=None)

        mock_read_status = MagicMock()
        mock_read_status.insert = AsyncMock()
        mock_read_status_class.return_value = mock_read_status

        result = await message_service.mark_multiple_messages_as_read(
            message_ids=["id1", "id2", "id3"],
            user_id=1,
            room_id=1
        )

        assert result == 3

    @patch('app.services.message_service.MessageReadStatus')
    async def test_mark_multiple_some_already_read(self, mock_read_status_class):
        """Should only mark unread messages"""
        # First two are already read, third is not
        existing_status = MagicMock()
        mock_read_status_class.find_one = AsyncMock(
            side_effect=[existing_status, existing_status, None]
        )

        mock_read_status = MagicMock()
        mock_read_status.insert = AsyncMock()
        mock_read_status_class.return_value = mock_read_status

        result = await message_service.mark_multiple_messages_as_read(
            message_ids=["id1", "id2", "id3"],
            user_id=1,
            room_id=1
        )

        assert result == 1  # Only one new read status created

    @patch('app.services.message_service.MessageReadStatus')
    async def test_mark_multiple_empty_list(self, mock_read_status_class):
        """Should return 0 for empty list"""
        result = await message_service.mark_multiple_messages_as_read(
            message_ids=[],
            user_id=1,
            room_id=1
        )

        assert result == 0


# =============================================================================
# Get Unread Messages Count Tests
# =============================================================================

class TestGetUnreadMessagesCount:
    """Tests for get_unread_messages_count function"""

    @patch('app.services.message_service.MessageReadStatus')
    @patch('app.services.message_service.Message')
    async def test_get_unread_count(self, mock_message, mock_read_status):
        """Should return count of unread messages"""
        # Create mock messages
        msg1 = MagicMock()
        msg1.id = "id1"
        msg1.user_id = 2  # From other user

        msg2 = MagicMock()
        msg2.id = "id2"
        msg2.user_id = 2  # From other user

        msg3 = MagicMock()
        msg3.id = "id3"
        msg3.user_id = 1  # From current user (should be excluded)

        mock_find_messages = MagicMock()
        mock_message.find.return_value = mock_find_messages
        mock_find_messages.to_list = AsyncMock(return_value=[msg1, msg2, msg3])

        # One message is read
        read_status = MagicMock()
        read_status.message_id = "id1"

        mock_find_read = MagicMock()
        mock_read_status.find.return_value = mock_find_read
        mock_find_read.to_list = AsyncMock(return_value=[read_status])

        result = await message_service.get_unread_messages_count(
            room_id=1,
            user_id=1
        )

        # msg2 is unread (msg1 is read, msg3 is from current user)
        assert result == 1

    @patch('app.services.message_service.MessageReadStatus')
    @patch('app.services.message_service.Message')
    async def test_get_unread_count_no_messages(self, mock_message, mock_read_status):
        """Should return 0 when no messages"""
        mock_find = MagicMock()
        mock_message.find.return_value = mock_find
        mock_find.to_list = AsyncMock(return_value=[])

        result = await message_service.get_unread_messages_count(
            room_id=1,
            user_id=1
        )

        assert result == 0

    @patch('app.services.message_service.MessageReadStatus')
    @patch('app.services.message_service.Message')
    async def test_get_unread_count_all_read(self, mock_message, mock_read_status):
        """Should return 0 when all messages are read"""
        msg1 = MagicMock()
        msg1.id = "id1"
        msg1.user_id = 2

        mock_find_messages = MagicMock()
        mock_message.find.return_value = mock_find_messages
        mock_find_messages.to_list = AsyncMock(return_value=[msg1])

        read_status = MagicMock()
        read_status.message_id = "id1"

        mock_find_read = MagicMock()
        mock_read_status.find.return_value = mock_find_read
        mock_find_read.to_list = AsyncMock(return_value=[read_status])

        result = await message_service.get_unread_messages_count(
            room_id=1,
            user_id=1
        )

        assert result == 0
