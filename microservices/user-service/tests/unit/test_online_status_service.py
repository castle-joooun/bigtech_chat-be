"""
Unit tests for online_status_service.py

Tests for Redis-based online status management.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services import online_status_service


# =============================================================================
# Redis Connection Tests
# =============================================================================

class TestGetRedis:
    """Tests for get_redis function"""

    @patch('app.services.online_status_service.redis')
    @patch('app.services.online_status_service.settings')
    async def test_get_redis_creates_connection(self, mock_settings, mock_redis):
        """Should create Redis connection on first call"""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_client = AsyncMock()
        mock_redis.from_url = AsyncMock(return_value=mock_redis_client)

        # Reset global client
        online_status_service.redis_client = None

        result = await online_status_service.get_redis()

        mock_redis.from_url.assert_called_once_with(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True
        )
        assert result == mock_redis_client

    @patch('app.services.online_status_service.redis')
    async def test_get_redis_reuses_connection(self, mock_redis):
        """Should reuse existing Redis connection"""
        mock_redis_client = AsyncMock()
        online_status_service.redis_client = mock_redis_client

        result = await online_status_service.get_redis()

        # Should not create new connection
        mock_redis.from_url.assert_not_called()
        assert result == mock_redis_client

        # Cleanup
        online_status_service.redis_client = None


class TestCloseRedis:
    """Tests for close_redis function"""

    async def test_close_redis_closes_connection(self):
        """Should close Redis connection and reset client"""
        mock_redis_client = AsyncMock()
        online_status_service.redis_client = mock_redis_client

        await online_status_service.close_redis()

        mock_redis_client.close.assert_called_once()
        assert online_status_service.redis_client is None

    async def test_close_redis_when_not_connected(self):
        """Should handle case when not connected"""
        online_status_service.redis_client = None

        # Should not raise error
        await online_status_service.close_redis()

        assert online_status_service.redis_client is None


# =============================================================================
# Online Status Tests
# =============================================================================

class TestSetOnline:
    """Tests for set_online function"""

    @patch('app.services.online_status_service.get_redis')
    async def test_set_online_with_session_id(self, mock_get_redis):
        """Should set user online with session ID"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await online_status_service.set_online(user_id=123, session_id="abc123")

        mock_redis.set.assert_called_once_with(
            "user:online:123",
            "abc123",
            ex=3600
        )

    @patch('app.services.online_status_service.get_redis')
    async def test_set_online_without_session_id(self, mock_get_redis):
        """Should set user online with default session ID"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await online_status_service.set_online(user_id=456)

        mock_redis.set.assert_called_once_with(
            "user:online:456",
            "default",
            ex=3600
        )

    @patch('app.services.online_status_service.get_redis')
    async def test_set_online_key_format(self, mock_get_redis):
        """Should use correct Redis key format"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await online_status_service.set_online(user_id=789)

        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "user:online:789"


class TestSetOffline:
    """Tests for set_offline function"""

    @patch('app.services.online_status_service.get_redis')
    async def test_set_offline(self, mock_get_redis):
        """Should delete user online status from Redis"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await online_status_service.set_offline(user_id=123)

        mock_redis.delete.assert_called_once_with("user:online:123")

    @patch('app.services.online_status_service.get_redis')
    async def test_set_offline_key_format(self, mock_get_redis):
        """Should use correct Redis key format"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await online_status_service.set_offline(user_id=456)

        call_args = mock_redis.delete.call_args
        assert call_args[0][0] == "user:online:456"


class TestIsOnline:
    """Tests for is_online function"""

    @patch('app.services.online_status_service.get_redis')
    async def test_is_online_when_online(self, mock_get_redis):
        """Should return True when user is online"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        mock_get_redis.return_value = mock_redis

        result = await online_status_service.is_online(user_id=123)

        assert result is True
        mock_redis.exists.assert_called_once_with("user:online:123")

    @patch('app.services.online_status_service.get_redis')
    async def test_is_online_when_offline(self, mock_get_redis):
        """Should return False when user is offline"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        mock_get_redis.return_value = mock_redis

        result = await online_status_service.is_online(user_id=456)

        assert result is False

    @patch('app.services.online_status_service.get_redis')
    async def test_is_online_key_format(self, mock_get_redis):
        """Should use correct Redis key format"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        mock_get_redis.return_value = mock_redis

        await online_status_service.is_online(user_id=789)

        call_args = mock_redis.exists.call_args
        assert call_args[0][0] == "user:online:789"


class TestUpdateActivity:
    """Tests for update_activity function"""

    @patch('app.services.online_status_service.get_redis')
    async def test_update_activity_when_online(self, mock_get_redis):
        """Should extend TTL when user is online"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True
        mock_get_redis.return_value = mock_redis

        await online_status_service.update_activity(user_id=123)

        mock_redis.expire.assert_called_once_with("user:online:123", 3600)

    @patch('app.services.online_status_service.get_redis')
    async def test_update_activity_when_offline(self, mock_get_redis):
        """Should not extend TTL when user is offline"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = False
        mock_get_redis.return_value = mock_redis

        await online_status_service.update_activity(user_id=456)

        mock_redis.expire.assert_not_called()

    @patch('app.services.online_status_service.get_redis')
    async def test_update_activity_key_format(self, mock_get_redis):
        """Should use correct Redis key format"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True
        mock_get_redis.return_value = mock_redis

        await online_status_service.update_activity(user_id=789)

        # Check both exists and expire calls use correct key
        mock_redis.exists.assert_called_with("user:online:789")
        mock_redis.expire.assert_called_with("user:online:789", 3600)


# =============================================================================
# Integration-like Tests (with mocked Redis)
# =============================================================================

class TestOnlineStatusFlow:
    """Integration-like tests for online status flow"""

    @patch('app.services.online_status_service.get_redis')
    async def test_full_online_offline_flow(self, mock_get_redis):
        """Should handle complete online/offline flow"""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        user_id = 123

        # User goes online
        await online_status_service.set_online(user_id, "session1")
        mock_redis.set.assert_called_with(f"user:online:{user_id}", "session1", ex=3600)

        # Check if online
        mock_redis.exists.return_value = 1
        is_online = await online_status_service.is_online(user_id)
        assert is_online is True

        # Update activity
        await online_status_service.update_activity(user_id)
        mock_redis.expire.assert_called_with(f"user:online:{user_id}", 3600)

        # User goes offline
        await online_status_service.set_offline(user_id)
        mock_redis.delete.assert_called_with(f"user:online:{user_id}")

        # Check if offline
        mock_redis.exists.return_value = 0
        is_online = await online_status_service.is_online(user_id)
        assert is_online is False
