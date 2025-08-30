"""Integration tests for /sr endpoint."""

import base64
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestSREndpoint:
    """Test /sr endpoint functionality."""

    @pytest.fixture
    def sample_config(self) -> dict[str, any]:
        """Sample proxy configuration for testing."""
        return {
            "users": ["dimonb", "testuser"],
            "subs": {
                "default": {
                    "DE_1_CONTABO": {
                        "protocol": "hy2",
                        "host": "de-1.contabo.v.dimonb.com",
                    }
                }
            },
        }

    @pytest.fixture
    def config_file(self, sample_config: dict[str, any]) -> Path:
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_config, f)
            return Path(f.name)

    def calculate_hash(self, username: str, salt: str) -> str:
        """Calculate authentication hash."""
        return hashlib.sha256(f"{username}.{salt}".encode()).hexdigest()

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_sr_endpoint_success(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test successful /sr endpoint request."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))
        mock_proxy_config.return_value = proxy_config_instance

        # Set global proxy_config
        import src.main

        src.main.proxy_config = proxy_config_instance

        client = TestClient(app)

        # Calculate valid hash
        username = "dimonb"
        expected_hash = self.calculate_hash(username, "test-salt")

        # Make request with authentication
        response = client.get(f"/sr?u={username}&hash={expected_hash}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

        # Check response is base64 encoded
        content = response.content.decode()
        try:
            decoded = base64.b64decode(content).decode()
            assert "hysteria2://" in decoded
        except Exception:
            pytest.fail("Response should be valid base64")

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_sr_endpoint_with_subscription(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test /sr endpoint with subscription parameter."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))
        mock_proxy_config.return_value = proxy_config_instance

        # Set global proxy_config
        import src.main

        src.main.proxy_config = proxy_config_instance

        client = TestClient(app)

        # Calculate valid hash
        username = "dimonb"
        expected_hash = self.calculate_hash(username, "test-salt")

        # Make request with subscription and custom password
        response = client.get(
            f"/sr?u={username}&hash={expected_hash}&sub=default&hash=custom-password"
        )

        assert response.status_code == 200

    @patch("src.main.proxy_config")
    def test_sr_endpoint_no_auth(self, mock_proxy_config, config_file: Path) -> None:
        """Test /sr endpoint without authentication."""
        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))
        mock_proxy_config.return_value = proxy_config_instance

        # Set global proxy_config
        import src.main

        src.main.proxy_config = proxy_config_instance

        client = TestClient(app)

        # Make request without authentication
        response = client.get("/sr")

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_sr_endpoint_invalid_user(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test /sr endpoint with invalid user."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))
        mock_proxy_config.return_value = proxy_config_instance

        # Set global proxy_config
        import src.main

        src.main.proxy_config = proxy_config_instance

        client = TestClient(app)

        # Calculate hash for invalid user
        username = "invaliduser"
        expected_hash = self.calculate_hash(username, "test-salt")

        # Make request with invalid user
        response = client.get(f"/sr?u={username}&hash={expected_hash}")

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_sr_endpoint_no_proxy_config(self) -> None:
        """Test /sr endpoint when proxy config is not available."""
        # Set global proxy_config to None
        import src.main

        src.main.proxy_config = None

        client = TestClient(app)

        # Make request
        response = client.get("/sr?u=test&hash=test")

        assert response.status_code == 500
        assert response.json()["detail"] == "Proxy configuration not available"
