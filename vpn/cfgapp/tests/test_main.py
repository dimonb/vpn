"""Tests for main application module."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.main import app


class TestMainApp:
    """Test main application functionality."""

    def test_health_check(self) -> None:
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "version": "0.1.0"}

    @pytest.mark.asyncio
    async def test_http_exception_propagation(self) -> None:
        """Test that HTTPException is properly propagated instead of being converted to 500."""
        from src.auth import require_auth

        # Create a mock request that will fail authentication
        request = Mock()
        request.url.query = ""

        # This should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"
