"""Tests for authentication module."""

import hashlib
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.auth import extract_template_tags, require_auth, verify_auth


class TestAuth:
    """Test authentication functions."""

    def test_extract_template_tags_empty(self) -> None:
        """Test extracting tags from empty template."""
        result = extract_template_tags("")
        assert result == []

    def test_extract_template_tags_no_tags(self) -> None:
        """Test extracting tags from template without tags."""
        template = "some content\nmore content"
        result = extract_template_tags(template)
        assert result == []

    def test_extract_template_tags_single_tag(self) -> None:
        """Test extracting single tag."""
        template = "#CLASH\nmixed-port: 7890"
        result = extract_template_tags(template)
        assert result == ["CLASH"]

    def test_extract_template_tags_multiple_tags(self) -> None:
        """Test extracting multiple tags."""
        template = "#CLASH,AUTH\nmixed-port: 7890"
        result = extract_template_tags(template)
        assert result == ["CLASH", "AUTH"]

    def test_extract_template_tags_with_spaces(self) -> None:
        """Test extracting tags with spaces."""
        template = "# CLASH , AUTH \nmixed-port: 7890"
        result = extract_template_tags(template)
        assert result == ["CLASH", "AUTH"]

    def test_verify_auth_missing_params(self) -> None:
        """Test auth verification with missing parameters."""
        request = Mock()
        request.url.query = ""
        
        result = verify_auth(request)
        assert result is False

    def test_verify_auth_invalid_hash(self) -> None:
        """Test auth verification with invalid hash."""
        request = Mock()
        request.url.query = "u=testuser&hash=invalidhash"
        
        result = verify_auth(request)
        assert result is False

    def test_require_auth_failure(self) -> None:
        """Test require_auth raises exception on failure."""
        request = Mock()
        request.url.query = ""
        
        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"


