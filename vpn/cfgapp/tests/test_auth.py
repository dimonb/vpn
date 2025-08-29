"""Tests for authentication module."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.auth import extract_template_tags, require_auth, verify_auth


class TestAuth:
    """Test authentication functionality."""

    @patch("src.auth.settings")
    def test_verify_auth_missing_params(self, mock_settings):
        """Test authentication with missing parameters."""
        mock_settings.salt = "test-salt"

        # Mock request without parameters
        mock_request = Mock()
        mock_request.url.query = ""

        result = verify_auth(mock_request)
        assert result is False

    @patch("src.auth.settings")
    def test_verify_auth_invalid_hash(self, mock_settings):
        """Test authentication with invalid hash."""
        mock_settings.salt = "test-salt"

        # Mock request with invalid hash
        mock_request = Mock()
        mock_request.url.query = "u=testuser&hash=invalid"

        result = verify_auth(mock_request)
        assert result is False

    @patch("src.auth.settings")
    def test_verify_auth_valid(self, mock_settings):
        """Test authentication with valid parameters."""
        mock_settings.salt = "test-salt"

        # Calculate expected hash
        import hashlib

        expected_hash = hashlib.sha256(b"testuser.test-salt").hexdigest()

        # Mock request with valid parameters
        mock_request = Mock()
        mock_request.url.query = f"u=testuser&hash={expected_hash}"

        result = verify_auth(mock_request)
        assert result is True

    @patch("src.auth.settings")
    def test_verify_auth_with_proxy_config_valid_user(self, mock_settings):
        """Test authentication with valid user in proxy config."""
        mock_settings.salt = "test-salt"

        # Calculate expected hash
        import hashlib

        expected_hash = hashlib.sha256(b"testuser.test-salt").hexdigest()

        # Mock request with valid parameters
        mock_request = Mock()
        mock_request.url.query = f"u=testuser&hash={expected_hash}"

        # Mock proxy config with valid user
        mock_proxy_config = Mock()
        mock_proxy_config.get_users.return_value = ["testuser", "otheruser"]

        result = verify_auth(mock_request, mock_proxy_config)
        assert result is True

    @patch("src.auth.settings")
    def test_verify_auth_with_proxy_config_invalid_user(self, mock_settings):
        """Test authentication with invalid user in proxy config."""
        mock_settings.salt = "test-salt"

        # Calculate expected hash
        import hashlib

        expected_hash = hashlib.sha256(b"testuser.test-salt").hexdigest()

        # Mock request with valid parameters
        mock_request = Mock()
        mock_request.url.query = f"u=testuser&hash={expected_hash}"

        # Mock proxy config without the user
        mock_proxy_config = Mock()
        mock_proxy_config.get_users.return_value = ["otheruser", "anotheruser"]

        result = verify_auth(mock_request, mock_proxy_config)
        assert result is False

    @patch("src.auth.settings")
    def test_verify_auth_with_proxy_config_no_users(self, mock_settings):
        """Test authentication with empty users list in proxy config."""
        mock_settings.salt = "test-salt"

        # Calculate expected hash
        import hashlib

        expected_hash = hashlib.sha256(b"testuser.test-salt").hexdigest()

        # Mock request with valid parameters
        mock_request = Mock()
        mock_request.url.query = f"u=testuser&hash={expected_hash}"

        # Mock proxy config with empty users list
        mock_proxy_config = Mock()
        mock_proxy_config.get_users.return_value = []

        result = verify_auth(mock_request, mock_proxy_config)
        assert result is False

    def test_require_auth_failure(self):
        """Test require_auth raises exception on failure."""
        # Mock request without parameters
        mock_request = Mock()
        mock_request.url.query = ""

        with pytest.raises(HTTPException) as exc_info:
            require_auth(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"

    def test_require_auth_with_proxy_config_failure(self):
        """Test require_auth raises exception when user not in proxy config."""
        # Mock request with valid hash but invalid user
        import hashlib

        expected_hash = hashlib.sha256(b"testuser.test-salt").hexdigest()

        mock_request = Mock()
        mock_request.url.query = f"u=testuser&hash={expected_hash}"

        # Mock proxy config without the user
        mock_proxy_config = Mock()
        mock_proxy_config.get_users.return_value = ["otheruser"]

        with pytest.raises(HTTPException) as exc_info:
            require_auth(mock_request, mock_proxy_config)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"

    def test_extract_template_tags_empty(self):
        """Test extracting tags from empty content."""
        result = extract_template_tags("")
        assert result == []

    def test_extract_template_tags_no_tags(self):
        """Test extracting tags from content without tags."""
        result = extract_template_tags("some content\nwithout tags")
        assert result == []

    def test_extract_template_tags_single_tag(self):
        """Test extracting single tag."""
        result = extract_template_tags("#CLASH\nsome content")
        assert result == ["CLASH"]

    def test_extract_template_tags_multiple_tags(self):
        """Test extracting multiple tags."""
        result = extract_template_tags("#CLASH,AUTH\nsome content")
        assert result == ["CLASH", "AUTH"]

    def test_extract_template_tags_with_spaces(self):
        """Test extracting tags with spaces."""
        result = extract_template_tags("# CLASH , AUTH \nsome content")
        assert result == ["CLASH", "AUTH"]
