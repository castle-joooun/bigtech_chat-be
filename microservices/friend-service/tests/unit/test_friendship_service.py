"""
Unit tests for FriendshipService

Tests for friend request operations, friendship management, and user search.
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.friendship import Friendship, BlockUser
from app.services.friendship_service import FriendshipService


# =============================================================================
# Send Friend Request Tests
# =============================================================================

class TestSendFriendRequest:
    """Tests for send_friend_request method"""

    async def test_send_request_success(self, db_session: AsyncSession, user_1: User, user_2: User):
        """Should create a pending friend request"""
        friendship = await FriendshipService.send_friend_request(
            db_session,
            requester_id=user_1.id,
            target_id=user_2.id
        )

        assert friendship is not None
        assert friendship.user_id_1 == user_1.id
        assert friendship.user_id_2 == user_2.id
        assert friendship.status == "pending"
        assert friendship.deleted_at is None

    async def test_send_request_duplicate_raises_error(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should raise error when friendship already exists"""
        with pytest.raises(ValueError, match="Friendship already exists or pending"):
            await FriendshipService.send_friend_request(
                db_session,
                requester_id=user_1.id,
                target_id=user_2.id
            )

    async def test_send_request_reverse_duplicate_raises_error(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should raise error when reverse friendship exists"""
        with pytest.raises(ValueError, match="Friendship already exists or pending"):
            await FriendshipService.send_friend_request(
                db_session,
                requester_id=user_2.id,
                target_id=user_1.id
            )

    async def test_send_request_to_accepted_friend_raises_error(
        self, db_session: AsyncSession, user_1: User, user_2: User, accepted_friendship: Friendship
    ):
        """Should raise error when already friends"""
        with pytest.raises(ValueError, match="Friendship already exists or pending"):
            await FriendshipService.send_friend_request(
                db_session,
                requester_id=user_1.id,
                target_id=user_2.id
            )


# =============================================================================
# Find Friendship Tests
# =============================================================================

class TestFindFriendship:
    """Tests for find_friendship method"""

    async def test_find_existing_friendship(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should find existing friendship"""
        result = await FriendshipService.find_friendship(
            db_session, user_1.id, user_2.id
        )

        assert result is not None
        assert result.id == pending_friendship.id

    async def test_find_friendship_reverse_order(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should find friendship regardless of user order"""
        result = await FriendshipService.find_friendship(
            db_session, user_2.id, user_1.id
        )

        assert result is not None
        assert result.id == pending_friendship.id

    async def test_find_nonexistent_friendship(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should return None when no friendship exists"""
        result = await FriendshipService.find_friendship(
            db_session, user_1.id, user_3.id
        )

        assert result is None

    async def test_find_deleted_friendship_returns_none(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should not find soft-deleted friendship"""
        # Soft delete the friendship
        pending_friendship.deleted_at = datetime.utcnow()
        await db_session.commit()

        result = await FriendshipService.find_friendship(
            db_session, user_1.id, user_2.id
        )

        assert result is None


# =============================================================================
# Accept Friend Request Tests
# =============================================================================

class TestAcceptFriendRequest:
    """Tests for accept_friend_request method"""

    async def test_accept_request_success(
        self, db_session: AsyncSession, user_2: User, pending_friendship: Friendship
    ):
        """Should accept pending friend request"""
        result = await FriendshipService.accept_friend_request(
            db_session,
            friendship_id=pending_friendship.id,
            user_id=user_2.id
        )

        assert result is not None
        assert result.status == "accepted"

    async def test_accept_request_by_requester_fails(
        self, db_session: AsyncSession, user_1: User, pending_friendship: Friendship
    ):
        """Should fail when requester tries to accept"""
        with pytest.raises(ValueError, match="Only the target user can accept"):
            await FriendshipService.accept_friend_request(
                db_session,
                friendship_id=pending_friendship.id,
                user_id=user_1.id
            )

    async def test_accept_nonexistent_request_fails(
        self, db_session: AsyncSession, user_2: User
    ):
        """Should fail when friendship doesn't exist"""
        with pytest.raises(ValueError, match="Friendship not found"):
            await FriendshipService.accept_friend_request(
                db_session,
                friendship_id=99999,
                user_id=user_2.id
            )

    async def test_accept_already_accepted_fails(
        self, db_session: AsyncSession, user_2: User, accepted_friendship: Friendship
    ):
        """Should fail when friendship is already accepted"""
        with pytest.raises(ValueError, match="Friendship request is not pending"):
            await FriendshipService.accept_friend_request(
                db_session,
                friendship_id=accepted_friendship.id,
                user_id=user_2.id
            )


# =============================================================================
# Reject Friend Request Tests
# =============================================================================

class TestRejectFriendRequest:
    """Tests for reject_friend_request method"""

    async def test_reject_request_success(
        self, db_session: AsyncSession, user_2: User, pending_friendship: Friendship
    ):
        """Should soft-delete pending friend request"""
        result = await FriendshipService.reject_friend_request(
            db_session,
            friendship_id=pending_friendship.id,
            user_id=user_2.id
        )

        assert result is True

        # Verify soft-deleted
        updated = await FriendshipService.get_friendship_by_id(
            db_session, pending_friendship.id
        )
        assert updated is None  # Should not be found (soft-deleted)

    async def test_reject_request_by_requester_fails(
        self, db_session: AsyncSession, user_1: User, pending_friendship: Friendship
    ):
        """Should fail when requester tries to reject"""
        with pytest.raises(ValueError, match="Only the target user can reject"):
            await FriendshipService.reject_friend_request(
                db_session,
                friendship_id=pending_friendship.id,
                user_id=user_1.id
            )

    async def test_reject_nonexistent_request_fails(
        self, db_session: AsyncSession, user_2: User
    ):
        """Should fail when friendship doesn't exist"""
        with pytest.raises(ValueError, match="Friendship not found"):
            await FriendshipService.reject_friend_request(
                db_session,
                friendship_id=99999,
                user_id=user_2.id
            )


# =============================================================================
# Accept/Reject by Requester ID Tests
# =============================================================================

class TestAcceptFriendRequestByRequester:
    """Tests for accept_friend_request_by_requester method"""

    async def test_accept_by_requester_id_success(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should accept friend request using requester ID"""
        result = await FriendshipService.accept_friend_request_by_requester(
            db_session,
            requester_user_id=user_1.id,
            current_user_id=user_2.id
        )

        assert result is not None
        assert result.status == "accepted"

    async def test_accept_by_requester_id_not_found(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should fail when friend request not found"""
        with pytest.raises(ValueError, match="Friend request not found"):
            await FriendshipService.accept_friend_request_by_requester(
                db_session,
                requester_user_id=user_1.id,
                current_user_id=user_3.id
            )


class TestRejectFriendRequestByRequester:
    """Tests for reject_friend_request_by_requester method"""

    async def test_reject_by_requester_id_success(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should reject friend request using requester ID"""
        result = await FriendshipService.reject_friend_request_by_requester(
            db_session,
            requester_user_id=user_1.id,
            current_user_id=user_2.id
        )

        assert result is True

    async def test_reject_by_requester_id_not_found(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should fail when friend request not found"""
        with pytest.raises(ValueError, match="Friend request not found"):
            await FriendshipService.reject_friend_request_by_requester(
                db_session,
                requester_user_id=user_1.id,
                current_user_id=user_3.id
            )


# =============================================================================
# Cancel Friend Request Tests
# =============================================================================

class TestCancelFriendRequest:
    """Tests for cancel_friend_request method"""

    async def test_cancel_request_success(
        self, db_session: AsyncSession, user_1: User, pending_friendship: Friendship
    ):
        """Should cancel pending friend request"""
        result = await FriendshipService.cancel_friend_request(
            db_session,
            friendship_id=pending_friendship.id,
            user_id=user_1.id
        )

        assert result is True

    async def test_cancel_by_target_fails(
        self, db_session: AsyncSession, user_2: User, pending_friendship: Friendship
    ):
        """Should fail when target tries to cancel"""
        with pytest.raises(ValueError, match="Only the requester can cancel"):
            await FriendshipService.cancel_friend_request(
                db_session,
                friendship_id=pending_friendship.id,
                user_id=user_2.id
            )

    async def test_cancel_accepted_request_fails(
        self, db_session: AsyncSession, user_1: User, accepted_friendship: Friendship
    ):
        """Should fail when trying to cancel accepted friendship"""
        with pytest.raises(ValueError, match="Only pending requests can be cancelled"):
            await FriendshipService.cancel_friend_request(
                db_session,
                friendship_id=accepted_friendship.id,
                user_id=user_1.id
            )


class TestCancelFriendRequestByTarget:
    """Tests for cancel_friend_request_by_target method"""

    async def test_cancel_by_target_id_success(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should cancel friend request using target ID"""
        result = await FriendshipService.cancel_friend_request_by_target(
            db_session,
            requester_id=user_1.id,
            target_user_id=user_2.id
        )

        assert result is True

    async def test_cancel_by_target_id_not_found(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should fail when friend request not found"""
        with pytest.raises(ValueError, match="Friend request not found"):
            await FriendshipService.cancel_friend_request_by_target(
                db_session,
                requester_id=user_1.id,
                target_user_id=user_3.id
            )


# =============================================================================
# Get Friendship by ID Tests
# =============================================================================

class TestGetFriendshipById:
    """Tests for get_friendship_by_id method"""

    async def test_get_existing_friendship(
        self, db_session: AsyncSession, pending_friendship: Friendship
    ):
        """Should return existing friendship"""
        result = await FriendshipService.get_friendship_by_id(
            db_session, pending_friendship.id
        )

        assert result is not None
        assert result.id == pending_friendship.id

    async def test_get_nonexistent_friendship(self, db_session: AsyncSession):
        """Should return None for nonexistent ID"""
        result = await FriendshipService.get_friendship_by_id(db_session, 99999)

        assert result is None

    async def test_get_deleted_friendship_returns_none(
        self, db_session: AsyncSession, pending_friendship: Friendship
    ):
        """Should not return soft-deleted friendship"""
        pending_friendship.deleted_at = datetime.utcnow()
        await db_session.commit()

        result = await FriendshipService.get_friendship_by_id(
            db_session, pending_friendship.id
        )

        assert result is None


# =============================================================================
# Get Friends List Tests
# =============================================================================

class TestGetFriendsList:
    """Tests for get_friends_list method"""

    async def test_get_friends_list_success(
        self, db_session: AsyncSession, user_1: User, user_2: User, accepted_friendship: Friendship
    ):
        """Should return list of friends"""
        result = await FriendshipService.get_friends_list(db_session, user_1.id)

        assert len(result) == 1
        friend, created_at = result[0]
        assert friend.id == user_2.id

    async def test_get_friends_list_empty(
        self, db_session: AsyncSession, user_3: User
    ):
        """Should return empty list when no friends"""
        result = await FriendshipService.get_friends_list(db_session, user_3.id)

        assert len(result) == 0

    async def test_get_friends_list_excludes_pending(
        self, db_session: AsyncSession, user_1: User, pending_friendship: Friendship
    ):
        """Should not include pending friendships"""
        result = await FriendshipService.get_friends_list(db_session, user_1.id)

        assert len(result) == 0

    async def test_get_friends_list_bidirectional(
        self, db_session: AsyncSession, user_1: User, user_2: User, accepted_friendship: Friendship
    ):
        """Should work for both users in friendship"""
        result_1 = await FriendshipService.get_friends_list(db_session, user_1.id)
        result_2 = await FriendshipService.get_friends_list(db_session, user_2.id)

        assert len(result_1) == 1
        assert len(result_2) == 1
        assert result_1[0][0].id == user_2.id
        assert result_2[0][0].id == user_1.id


# =============================================================================
# Get Friend Requests Tests
# =============================================================================

class TestGetFriendRequests:
    """Tests for get_friend_requests method"""

    async def test_get_received_requests(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should return received friend requests"""
        received, sent = await FriendshipService.get_friend_requests(
            db_session, user_2.id
        )

        assert len(received) == 1
        assert len(sent) == 0
        assert received[0][0].id == pending_friendship.id

    async def test_get_sent_requests(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should return sent friend requests"""
        received, sent = await FriendshipService.get_friend_requests(
            db_session, user_1.id
        )

        assert len(received) == 0
        assert len(sent) == 1
        assert sent[0][0].id == pending_friendship.id

    async def test_get_requests_empty(self, db_session: AsyncSession, user_3: User):
        """Should return empty lists when no requests"""
        received, sent = await FriendshipService.get_friend_requests(
            db_session, user_3.id
        )

        assert len(received) == 0
        assert len(sent) == 0


# =============================================================================
# Are Friends Tests
# =============================================================================

class TestAreFriends:
    """Tests for are_friends method"""

    async def test_are_friends_accepted(
        self, db_session: AsyncSession, user_1: User, user_2: User, accepted_friendship: Friendship
    ):
        """Should return True for accepted friendship"""
        result = await FriendshipService.are_friends(
            db_session, user_1.id, user_2.id
        )

        assert result is True

    async def test_are_friends_pending(
        self, db_session: AsyncSession, user_1: User, user_2: User, pending_friendship: Friendship
    ):
        """Should return False for pending friendship"""
        result = await FriendshipService.are_friends(
            db_session, user_1.id, user_2.id
        )

        assert result is False

    async def test_are_friends_none(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should return False when no friendship exists"""
        result = await FriendshipService.are_friends(
            db_session, user_1.id, user_3.id
        )

        assert result is False

    async def test_are_friends_bidirectional(
        self, db_session: AsyncSession, user_1: User, user_2: User, accepted_friendship: Friendship
    ):
        """Should work regardless of user order"""
        result_1 = await FriendshipService.are_friends(
            db_session, user_1.id, user_2.id
        )
        result_2 = await FriendshipService.are_friends(
            db_session, user_2.id, user_1.id
        )

        assert result_1 is True
        assert result_2 is True


# =============================================================================
# Search Users for Friend Tests
# =============================================================================

class TestSearchUsersForFriend:
    """Tests for search_users_for_friend method"""

    async def test_search_by_username(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should find users by username"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="user3"
        )

        assert len(result) == 1
        assert result[0].id == user_3.id

    async def test_search_by_email(
        self, db_session: AsyncSession, user_1: User, user_3: User
    ):
        """Should find users by email"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="user3@example"
        )

        assert len(result) == 1
        assert result[0].id == user_3.id

    async def test_search_excludes_self(
        self, db_session: AsyncSession, user_1: User
    ):
        """Should exclude current user from results"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="user1"
        )

        assert len(result) == 0

    async def test_search_excludes_friends(
        self, db_session: AsyncSession, user_1: User, user_2: User, accepted_friendship: Friendship
    ):
        """Should exclude already friends from results"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="user2"
        )

        assert len(result) == 0

    async def test_search_excludes_blocked_users(
        self, db_session: AsyncSession, user_1: User, user_3: User, blocked_user_relationship: BlockUser
    ):
        """Should exclude blocked users from results"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="user3"
        )

        assert len(result) == 0

    async def test_search_excludes_inactive_users(
        self, db_session: AsyncSession, user_1: User, inactive_user: User
    ):
        """Should exclude inactive users from results"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="inactive"
        )

        assert len(result) == 0

    async def test_search_respects_limit(
        self, db_session: AsyncSession, user_1: User, user_2: User, user_3: User
    ):
        """Should respect limit parameter"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="user",
            limit=1
        )

        assert len(result) <= 1

    async def test_search_no_results(self, db_session: AsyncSession, user_1: User):
        """Should return empty list when no matches"""
        result = await FriendshipService.search_users_for_friend(
            db_session,
            current_user_id=user_1.id,
            query="nonexistent_xyz"
        )

        assert len(result) == 0
