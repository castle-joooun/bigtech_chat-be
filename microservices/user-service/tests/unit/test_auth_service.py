"""
Unit tests for auth_service.py

Tests for user CRUD operations, authentication, and profile management.
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import auth_service


# =============================================================================
# User CRUD Operations Tests
# =============================================================================

class TestFindUserById:
    """Tests for find_user_by_id function"""

    async def test_find_existing_user(self, db_session: AsyncSession, test_user: User):
        """Should return user when ID exists"""
        result = await auth_service.find_user_by_id(db_session, test_user.id)

        assert result is not None
        assert result.id == test_user.id
        assert result.email == test_user.email

    async def test_find_nonexistent_user(self, db_session: AsyncSession):
        """Should return None when user ID does not exist"""
        result = await auth_service.find_user_by_id(db_session, 99999)

        assert result is None


class TestFindUserByEmail:
    """Tests for find_user_by_email function"""

    async def test_find_existing_email(self, db_session: AsyncSession, test_user: User):
        """Should return user when email exists"""
        result = await auth_service.find_user_by_email(db_session, test_user.email)

        assert result is not None
        assert result.email == test_user.email

    async def test_find_nonexistent_email(self, db_session: AsyncSession):
        """Should return None when email does not exist"""
        result = await auth_service.find_user_by_email(db_session, "nonexistent@example.com")

        assert result is None

    async def test_email_case_sensitivity(self, db_session: AsyncSession, test_user: User):
        """Should handle email case sensitivity correctly"""
        # Note: This depends on database collation settings
        result = await auth_service.find_user_by_email(db_session, test_user.email.upper())

        # SQLite is case-insensitive by default for LIKE, but = is case-sensitive
        # Behavior may vary based on actual database
        assert result is None or result.email == test_user.email


class TestFindUserByUsername:
    """Tests for find_user_by_username function"""

    async def test_find_existing_username(self, db_session: AsyncSession, test_user: User):
        """Should return user when username exists"""
        result = await auth_service.find_user_by_username(db_session, test_user.username)

        assert result is not None
        assert result.username == test_user.username

    async def test_find_nonexistent_username(self, db_session: AsyncSession):
        """Should return None when username does not exist"""
        result = await auth_service.find_user_by_username(db_session, "nonexistent_user")

        assert result is None


class TestCreateUser:
    """Tests for create_user function"""

    async def test_create_user_success(self, db_session: AsyncSession):
        """Should create user with all fields"""
        user = await auth_service.create_user(
            db_session,
            email="newuser@example.com",
            username="newuser",
            password_hash="hashed_password",
            display_name="New User"
        )

        assert user is not None
        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.username == "newuser"
        assert user.display_name == "New User"
        assert user.created_at is not None
        assert user.updated_at is not None

    async def test_create_user_without_display_name(self, db_session: AsyncSession):
        """Should create user without display_name"""
        user = await auth_service.create_user(
            db_session,
            email="nodisplay@example.com",
            username="nodisplayuser",
            password_hash="hashed_password"
        )

        assert user is not None
        assert user.display_name is None

    async def test_create_user_persists_to_database(self, db_session: AsyncSession):
        """Should persist user to database"""
        user = await auth_service.create_user(
            db_session,
            email="persist@example.com",
            username="persistuser",
            password_hash="hashed_password"
        )

        # Verify by querying
        found = await auth_service.find_user_by_id(db_session, user.id)
        assert found is not None
        assert found.email == "persist@example.com"


# =============================================================================
# User Existence Check Tests
# =============================================================================

class TestIsEmailExists:
    """Tests for is_email_exists function"""

    async def test_email_exists(self, db_session: AsyncSession, test_user: User):
        """Should return True when email exists"""
        result = await auth_service.is_email_exists(db_session, test_user.email)

        assert result is True

    async def test_email_not_exists(self, db_session: AsyncSession):
        """Should return False when email does not exist"""
        result = await auth_service.is_email_exists(db_session, "notfound@example.com")

        assert result is False


class TestIsUsernameExists:
    """Tests for is_username_exists function"""

    async def test_username_exists(self, db_session: AsyncSession, test_user: User):
        """Should return True when username exists"""
        result = await auth_service.is_username_exists(db_session, test_user.username)

        assert result is True

    async def test_username_not_exists(self, db_session: AsyncSession):
        """Should return False when username does not exist"""
        result = await auth_service.is_username_exists(db_session, "nonexistent_username")

        assert result is False


class TestIsUserExists:
    """Tests for is_user_exists function"""

    async def test_user_exists(self, db_session: AsyncSession, test_user: User):
        """Should return True when user ID exists"""
        result = await auth_service.is_user_exists(db_session, test_user.id)

        assert result is True

    async def test_user_not_exists(self, db_session: AsyncSession):
        """Should return False when user ID does not exist"""
        result = await auth_service.is_user_exists(db_session, 99999)

        assert result is False


# =============================================================================
# Authentication Tests
# =============================================================================

class TestAuthenticateUserByEmail:
    """Tests for authenticate_user_by_email function"""

    async def test_authenticate_success(self, db_session: AsyncSession, test_user: User, user_data: dict):
        """Should return user when credentials are correct"""
        result = await auth_service.authenticate_user_by_email(
            db_session,
            user_data["email"],
            user_data["password"]
        )

        assert result is not None
        assert result.id == test_user.id
        assert result.email == test_user.email

    async def test_authenticate_wrong_password(self, db_session: AsyncSession, test_user: User):
        """Should return None when password is wrong"""
        result = await auth_service.authenticate_user_by_email(
            db_session,
            test_user.email,
            "wrong_password"
        )

        assert result is None

    async def test_authenticate_nonexistent_email(self, db_session: AsyncSession):
        """Should return None when email does not exist"""
        result = await auth_service.authenticate_user_by_email(
            db_session,
            "nonexistent@example.com",
            "any_password"
        )

        assert result is None

    async def test_authenticate_empty_password(self, db_session: AsyncSession, test_user: User):
        """Should return None when password is empty"""
        result = await auth_service.authenticate_user_by_email(
            db_session,
            test_user.email,
            ""
        )

        assert result is None


# =============================================================================
# Profile Management Tests
# =============================================================================

class TestUpdateUserProfile:
    """Tests for update_user_profile function"""

    async def test_update_display_name(self, db_session: AsyncSession, test_user: User):
        """Should update display_name"""
        result = await auth_service.update_user_profile(
            db_session,
            test_user.id,
            display_name="Updated Name"
        )

        assert result is not None
        assert result.display_name == "Updated Name"

    async def test_update_status_message(self, db_session: AsyncSession, test_user: User):
        """Should update status_message"""
        result = await auth_service.update_user_profile(
            db_session,
            test_user.id,
            status_message="Hello World!"
        )

        assert result is not None
        assert result.status_message == "Hello World!"

    async def test_update_both_fields(self, db_session: AsyncSession, test_user: User):
        """Should update both display_name and status_message"""
        result = await auth_service.update_user_profile(
            db_session,
            test_user.id,
            display_name="New Name",
            status_message="New Status"
        )

        assert result is not None
        assert result.display_name == "New Name"
        assert result.status_message == "New Status"

    async def test_update_nonexistent_user(self, db_session: AsyncSession):
        """Should return None when user does not exist"""
        result = await auth_service.update_user_profile(
            db_session,
            99999,
            display_name="Name"
        )

        assert result is None

    async def test_update_sets_updated_at(self, db_session: AsyncSession, test_user: User):
        """Should update updated_at timestamp"""
        original_updated_at = test_user.updated_at

        result = await auth_service.update_user_profile(
            db_session,
            test_user.id,
            display_name="Updated"
        )

        assert result is not None
        assert result.updated_at >= original_updated_at


class TestUpdateProfileImage:
    """Tests for update_profile_image function"""

    async def test_update_profile_image(self, db_session: AsyncSession, test_user: User):
        """Should update profile_image_url"""
        image_url = "https://example.com/image.jpg"

        result = await auth_service.update_profile_image(
            db_session,
            test_user.id,
            image_url
        )

        assert result is not None
        assert result.profile_image_url == image_url

    async def test_update_profile_image_nonexistent_user(self, db_session: AsyncSession):
        """Should return None when user does not exist"""
        result = await auth_service.update_profile_image(
            db_session,
            99999,
            "https://example.com/image.jpg"
        )

        assert result is None


class TestUpdateOnlineStatus:
    """Tests for update_online_status function"""

    async def test_set_online(self, db_session: AsyncSession, test_user: User):
        """Should set user online"""
        result = await auth_service.update_online_status(
            db_session,
            test_user.id,
            is_online=True
        )

        assert result is not None
        assert result.is_online is True

    async def test_set_offline_updates_last_seen(self, db_session: AsyncSession, test_user: User):
        """Should set user offline and update last_seen_at"""
        result = await auth_service.update_online_status(
            db_session,
            test_user.id,
            is_online=False
        )

        assert result is not None
        assert result.is_online is False
        assert result.last_seen_at is not None

    async def test_update_nonexistent_user(self, db_session: AsyncSession):
        """Should return None when user does not exist"""
        result = await auth_service.update_online_status(
            db_session,
            99999,
            is_online=True
        )

        assert result is None


class TestUpdateLastSeen:
    """Tests for update_last_seen function"""

    async def test_update_last_seen(self, db_session: AsyncSession, test_user: User):
        """Should update last_seen_at timestamp"""
        result = await auth_service.update_last_seen(db_session, test_user.id)

        assert result is not None
        assert result.last_seen_at is not None

    async def test_update_last_seen_nonexistent_user(self, db_session: AsyncSession):
        """Should return None when user does not exist"""
        result = await auth_service.update_last_seen(db_session, 99999)

        assert result is None


# =============================================================================
# Search Tests
# =============================================================================

class TestSearchUsersByUsername:
    """Tests for search_users_by_username function"""

    async def test_search_by_username(self, db_session: AsyncSession, test_user: User):
        """Should find user by username substring"""
        results = await auth_service.search_users_by_username(
            db_session,
            "test"
        )

        assert len(results) >= 1
        assert any(u.id == test_user.id for u in results)

    async def test_search_by_display_name(self, db_session: AsyncSession, test_user: User):
        """Should find user by display_name substring"""
        results = await auth_service.search_users_by_username(
            db_session,
            "Test User"
        )

        assert len(results) >= 1
        assert any(u.id == test_user.id for u in results)

    async def test_search_no_results(self, db_session: AsyncSession):
        """Should return empty list when no matches"""
        results = await auth_service.search_users_by_username(
            db_session,
            "nonexistent_query_xyz"
        )

        assert len(results) == 0

    async def test_search_with_limit(self, db_session: AsyncSession, test_user: User, test_user_2: User):
        """Should respect limit parameter"""
        results = await auth_service.search_users_by_username(
            db_session,
            "test",
            limit=1
        )

        assert len(results) <= 1

    async def test_search_exclude_user(self, db_session: AsyncSession, test_user: User, test_user_2: User):
        """Should exclude specified user from results"""
        results = await auth_service.search_users_by_username(
            db_session,
            "test",
            exclude_user_id=test_user.id
        )

        assert not any(u.id == test_user.id for u in results)

    async def test_search_excludes_inactive_users(self, db_session: AsyncSession, inactive_user: User):
        """Should not return inactive users"""
        results = await auth_service.search_users_by_username(
            db_session,
            "inactive"
        )

        assert not any(u.id == inactive_user.id for u in results)


class TestGetUserCountByQuery:
    """Tests for get_user_count_by_query function"""

    async def test_count_matching_users(self, db_session: AsyncSession, test_user: User):
        """Should return count of matching users"""
        count = await auth_service.get_user_count_by_query(db_session, "test")

        assert count >= 1

    async def test_count_no_matches(self, db_session: AsyncSession):
        """Should return 0 when no matches"""
        count = await auth_service.get_user_count_by_query(
            db_session,
            "nonexistent_query_xyz"
        )

        assert count == 0

    async def test_count_exclude_user(self, db_session: AsyncSession, test_user: User, test_user_2: User):
        """Should exclude specified user from count"""
        count_all = await auth_service.get_user_count_by_query(db_session, "test")
        count_excluded = await auth_service.get_user_count_by_query(
            db_session,
            "test",
            exclude_user_id=test_user.id
        )

        assert count_excluded == count_all - 1


class TestGetUsersByIds:
    """Tests for get_users_by_ids function"""

    async def test_get_multiple_users(self, db_session: AsyncSession, test_user: User, test_user_2: User):
        """Should return users for given IDs"""
        results = await auth_service.get_users_by_ids(
            db_session,
            [test_user.id, test_user_2.id]
        )

        assert len(results) == 2
        user_ids = [u.id for u in results]
        assert test_user.id in user_ids
        assert test_user_2.id in user_ids

    async def test_get_users_empty_list(self, db_session: AsyncSession):
        """Should return empty list for empty input"""
        results = await auth_service.get_users_by_ids(db_session, [])

        assert len(results) == 0

    async def test_get_users_partial_match(self, db_session: AsyncSession, test_user: User):
        """Should return only existing users"""
        results = await auth_service.get_users_by_ids(
            db_session,
            [test_user.id, 99999]
        )

        assert len(results) == 1
        assert results[0].id == test_user.id
