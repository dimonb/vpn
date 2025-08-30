"""Tests for subscription page functionality."""

import base64
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestSubscriptionPage:
    """Test subscription page functionality."""

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
    def test_subscription_page_success(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test successful subscription page request."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012
        mock_settings.base_url = "https://test.example.com"

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
        response = client.get(f"/sub?u={username}&hash={expected_hash}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

        # Check response contains expected elements
        content = response.content.decode()
        assert "ShadowRocket" in content
        assert "Subscription Configuration" in content
        assert "sub://" in content
        assert "data:image/png;base64," in content  # QR code
        assert "Copy to Clipboard" in content
        assert username in content

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_subscription_page_with_subscription(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test subscription page with specific subscription."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012
        mock_settings.base_url = "https://test.example.com"

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

        # Make request with subscription parameter
        response = client.get(f"/sub?u={username}&hash={expected_hash}&sub=default")

        assert response.status_code == 200
        content = response.content.decode()
        assert "default" in content

    @patch("src.main.proxy_config")
    def test_subscription_page_no_auth(
        self, mock_proxy_config, config_file: Path
    ) -> None:
        """Test subscription page without authentication."""
        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))
        mock_proxy_config.return_value = proxy_config_instance

        # Set global proxy_config
        import src.main

        src.main.proxy_config = proxy_config_instance

        client = TestClient(app)

        # Make request without authentication
        response = client.get("/sub")

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_subscription_page_no_proxy_config(self) -> None:
        """Test subscription page when proxy config is not available."""
        # Set global proxy_config to None
        import src.main

        src.main.proxy_config = None

        client = TestClient(app)

        # Make request
        response = client.get("/sub?u=test&hash=test")

        assert response.status_code == 500
        assert response.json()["detail"] == "Proxy configuration not available"

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_subscription_url_generation(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test that subscription URL is generated correctly."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))

        # Test URL generation
        base_url = "https://example.com"
        sub_url = proxy_config_instance.generate_subscription_url(base_url, "testuser")

        # Check format
        assert sub_url.startswith("sub://")
        assert "?udp=1&allowInsecure=1#default" in sub_url

        # Decode base64 part
        b64_part = sub_url.split("sub://")[1].split("?")[0]
        decoded_url = base64.b64decode(b64_part).decode()
        assert decoded_url == f"{base_url}/sr?u=testuser"

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_subscription_url_with_params(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test subscription URL generation with parameters."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))

        # Test URL generation with parameters
        base_url = "https://example.com"
        sub_url = proxy_config_instance.generate_subscription_url(
            base_url, "testuser", "premium", "custom-password"
        )

        # Decode base64 part
        b64_part = sub_url.split("sub://")[1].split("?")[0]
        decoded_url = base64.b64decode(b64_part).decode()

        # Should contain parameters
        assert "u=testuser" in decoded_url
        assert "sub=premium" in decoded_url
        assert "hash=custom-password" in decoded_url

        # Should end with subscription name fragment
        assert sub_url.endswith("#premium")

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_qr_code_generation(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test QR code generation."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        # Create proxy config
        from src.proxy_config import ProxyConfig

        proxy_config_instance = ProxyConfig(str(config_file))

        # Test QR code generation
        test_data = "sub://dGVzdA==?udp=1&allowInsecure=1"
        qr_b64 = proxy_config_instance.generate_qr_code(test_data)

        # Should be valid base64
        try:
            qr_data = base64.b64decode(qr_b64)
            # Should be PNG data (starts with PNG signature)
            assert qr_data.startswith(b"\x89PNG")
        except Exception:
            pytest.fail("QR code should be valid base64 PNG data")

    @patch("src.main.proxy_config")
    @patch("src.config.settings")
    @patch("src.auth.settings")
    def test_subscription_page_fallback_base_url(
        self, mock_auth_settings, mock_settings, mock_proxy_config, config_file: Path
    ) -> None:
        """Test subscription page with fallback base URL when BASE_URL is not set."""
        # Setup mocks
        mock_auth_settings.salt = "test-salt"
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012
        mock_settings.base_url = ""  # Empty base URL to trigger fallback

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
        response = client.get(f"/sub?u={username}&hash={expected_hash}")

        assert response.status_code == 200
        content = response.content.decode()

        # Should fallback to request-based URL (testserver in this case)
        assert "sub://" in content
