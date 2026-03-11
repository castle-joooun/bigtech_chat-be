"""
Unit tests for auth utilities (utils/auth.py)

Tests for password hashing, validation, and JWT token operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.utils.auth import (
    verify_password,
    get_password_hash,
    verify_password_async,
    get_password_hash_async,
    validate_password,
    create_access_token,
    decode_access_token
)


# =============================================================================
# Password Hashing Tests
# =============================================================================

class TestPasswordHashing:
    """Tests for password hashing functions"""

    def test_get_password_hash(self):
        """Should return a bcrypt hash"""
        password = "Test123!@#"
        hashed = get_password_hash(password)

        assert hashed is not None
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self):
        """Should return True for correct password"""
        password = "Test123!@#"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Should return False for incorrect password"""
        password = "Test123!@#"
        hashed = get_password_hash(password)

        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Should generate different hashes for same password (salt)"""
        password = "Test123!@#"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestAsyncPasswordHashing:
    """Tests for async password hashing functions"""

    async def test_get_password_hash_async(self):
        """Should return a bcrypt hash asynchronously"""
        password = "Test123!@#"
        hashed = await get_password_hash_async(password)

        assert hashed is not None
        assert hashed != password
        assert hashed.startswith("$2b$")

    async def test_verify_password_async_correct(self):
        """Should return True for correct password asynchronously"""
        password = "Test123!@#"
        hashed = await get_password_hash_async(password)

        result = await verify_password_async(password, hashed)
        assert result is True

    async def test_verify_password_async_incorrect(self):
        """Should return False for incorrect password asynchronously"""
        password = "Test123!@#"
        hashed = await get_password_hash_async(password)

        result = await verify_password_async("wrong_password", hashed)
        assert result is False


# =============================================================================
# Password Validation Tests
# =============================================================================

class TestValidatePassword:
    """Tests for password validation function"""

    def test_valid_password(self):
        """Should return True for valid password"""
        assert validate_password("Test123!@#") is True
        assert validate_password("Abc12345!") is True
        assert validate_password("P@ssw0rd") is True

    def test_password_too_short(self):
        """Should return False for password shorter than 8 characters"""
        assert validate_password("Te1!") is False
        assert validate_password("Test1!") is False
        assert validate_password("Ab1!234") is False  # 7 chars

    def test_password_too_long(self):
        """Should return False for password longer than 16 characters"""
        assert validate_password("Test123!@#abcdefg") is False  # 17 chars
        assert validate_password("A" * 17 + "1!") is False

    def test_password_no_letter(self):
        """Should return False for password without letters"""
        assert validate_password("12345678!") is False
        assert validate_password("!@#$%^&*1") is False

    def test_password_no_digit(self):
        """Should return False for password without digits"""
        assert validate_password("Testtest!") is False
        assert validate_password("Password!@#") is False

    def test_password_no_special_char(self):
        """Should return False for password without special characters"""
        assert validate_password("Test1234") is False
        assert validate_password("Password123") is False

    def test_password_boundary_length(self):
        """Should handle boundary lengths correctly"""
        # Exactly 8 characters
        assert validate_password("Test12!a") is True

        # Exactly 16 characters
        assert validate_password("Test1234!@#abcde") is True

    def test_various_special_characters(self):
        """Should accept various special characters"""
        special_chars = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+']

        for char in special_chars:
            password = f"Test123{char}"
            assert validate_password(password) is True, f"Failed for special char: {char}"


# =============================================================================
# JWT Token Tests
# =============================================================================

class TestCreateAccessToken:
    """Tests for JWT access token creation"""

    @patch('app.utils.auth.settings')
    def test_create_access_token(self, mock_settings):
        """Should create a valid JWT token"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"
        mock_settings.access_token_expire_hours = 2

        token = create_access_token({"sub": "user@example.com", "user_id": 1})

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @patch('app.utils.auth.settings')
    def test_create_access_token_with_custom_expiry(self, mock_settings):
        """Should create token with custom expiry"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"

        token = create_access_token(
            {"sub": "user@example.com"},
            expires_delta=timedelta(hours=5)
        )

        assert token is not None

    @patch('app.utils.auth.settings')
    def test_token_contains_type(self, mock_settings):
        """Should include type in token payload"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"
        mock_settings.access_token_expire_hours = 2

        token = create_access_token({"sub": "user@example.com"})
        decoded = decode_access_token(token)

        assert decoded is not None
        assert decoded.get("type") == "access"


class TestDecodeAccessToken:
    """Tests for JWT access token decoding"""

    @patch('app.utils.auth.settings')
    def test_decode_valid_token(self, mock_settings):
        """Should decode a valid token"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"
        mock_settings.access_token_expire_hours = 2

        token = create_access_token({"sub": "user@example.com", "user_id": 1})
        decoded = decode_access_token(token)

        assert decoded is not None
        assert decoded["sub"] == "user@example.com"
        assert decoded["user_id"] == 1

    @patch('app.utils.auth.settings')
    def test_decode_invalid_token(self, mock_settings):
        """Should return None for invalid token"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"

        decoded = decode_access_token("invalid.token.here")

        assert decoded is None

    @patch('app.utils.auth.settings')
    def test_decode_expired_token(self, mock_settings):
        """Should return None for expired token"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"

        # Create token that's already expired
        token = create_access_token(
            {"sub": "user@example.com"},
            expires_delta=timedelta(seconds=-1)
        )
        decoded = decode_access_token(token)

        assert decoded is None

    @patch('app.utils.auth.settings')
    def test_decode_wrong_secret(self, mock_settings):
        """Should return None when decoded with wrong secret"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"
        mock_settings.access_token_expire_hours = 2

        token = create_access_token({"sub": "user@example.com"})

        # Try to decode with different secret
        mock_settings.secret_key = "wrong-secret-key"
        decoded = decode_access_token(token)

        assert decoded is None

    @patch('app.utils.auth.settings')
    def test_decode_token_preserves_data(self, mock_settings):
        """Should preserve all data in token"""
        mock_settings.secret_key = "test-secret-key"
        mock_settings.algorithm = "HS256"
        mock_settings.access_token_expire_hours = 2

        data = {
            "sub": "user@example.com",
            "user_id": 123,
            "username": "testuser",
            "role": "admin"
        }

        token = create_access_token(data)
        decoded = decode_access_token(token)

        assert decoded is not None
        assert decoded["sub"] == data["sub"]
        assert decoded["user_id"] == data["user_id"]
        assert decoded["username"] == data["username"]
        assert decoded["role"] == data["role"]
