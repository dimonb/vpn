"""Tests for ShadowRocket subscription functionality."""

import base64
import json
import tempfile
import urllib.parse
from pathlib import Path
from unittest.mock import patch

import pytest

from src.proxy_config import ProxyConfig


class TestShadowRocketSubscription:
    """Test ShadowRocket subscription functionality."""

    @pytest.fixture
    def sample_config(self) -> dict[str, any]:
        """Sample proxy configuration for testing."""
        return {
            "users": ["dimonb", "diakon", "ivan", "petrov"],
            "subs": {
                "default": {
                    "DE_1_CONTABO": {
                        "protocol": "hy2",
                        "host": "de-1.contabo.v.dimonb.com",
                    },
                    "US_1_VULTR": {
                        "protocol": "vmess",
                        "host": "us-1.vultr.v.dimonb.com",
                    },
                },
                "premium": {
                    "SG_1_LINODE": {
                        "protocol": "vless",
                        "host": "sg-1.linode.v.dimonb.com",
                    }
                },
                "v2": {
                    "DE_1_CONTABO_V2": {
                        "protocol": "hy2-v2",
                        "host": "de-1.contabo.v.dimonb.com",
                    },
                },
            },
        }

    @pytest.fixture
    def config_file(self, sample_config: dict[str, any]) -> Path:
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_config, f)
            return Path(f.name)

    @patch("src.proxy_config.settings")
    def test_generate_shadowrocket_subscription_default(
        self, mock_settings, config_file: Path
    ) -> None:
        """Test ShadowRocket subscription generation for default subscription."""
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        proxy_config = ProxyConfig(str(config_file))
        subscription_b64 = proxy_config.generate_shadowrocket_subscription()

        # Decode base64 to check content
        subscription_content = base64.b64decode(subscription_b64).decode()
        urls = subscription_content.strip().split("\n")

        # Should have 2 URLs (one per proxy)
        assert len(urls) == 2

        # Check Hysteria2 URL
        hy2_urls = [url for url in urls if url.startswith("hysteria2://")]
        assert len(hy2_urls) == 1
        hy2_url = hy2_urls[0]

        # Parse Hysteria2 URL
        assert "de-1.contabo.v.dimonb.com:47012" in hy2_url
        assert "peer=i.am.com" in hy2_url
        assert "obfs-password=test-obfs-password" in hy2_url
        assert "#de_1_contabo.hy2" in hy2_url

        # Check VMess URL
        vmess_urls = [url for url in urls if url.startswith("vmess://")]
        assert len(vmess_urls) == 1
        vmess_url = vmess_urls[0]

        # Parse VMess URL
        assert "vmess://" in vmess_url
        assert "fragment=1,40-60,30-50" in vmess_url

        # Decode VMess config
        vmess_b64 = vmess_url.split("vmess://")[1].split("?")[0]
        vmess_config = json.loads(base64.b64decode(vmess_b64).decode())

        assert vmess_config["add"] == "us-1.vultr.v.dimonb.com"
        assert vmess_config["ps"] == "us_1_vultr"
        assert vmess_config["net"] == "ws"
        assert vmess_config["tls"] == "tls"

    @patch("src.proxy_config.settings")
    def test_generate_shadowrocket_subscription_premium(
        self, mock_settings, config_file: Path
    ) -> None:
        """Test ShadowRocket subscription generation for premium subscription."""
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        proxy_config = ProxyConfig(str(config_file))
        subscription_b64 = proxy_config.generate_shadowrocket_subscription("premium")

        # Decode base64 to check content
        subscription_content = base64.b64decode(subscription_b64).decode()
        urls = subscription_content.strip().split("\n")

        # Should have 1 URL (one per proxy)
        assert len(urls) == 1

        # Check VLESS URL
        vless_urls = [url for url in urls if url.startswith("vless://")]
        assert len(vless_urls) == 1
        vless_url = vless_urls[0]

        # Parse VLESS URL
        assert "sg-1.linode.v.dimonb.com" in vless_url
        assert "type=ws" in vless_url
        assert "security=tls" in vless_url
        assert "#sg_1_linode" in vless_url

    @patch("src.proxy_config.settings")
    def test_generate_shadowrocket_subscription_with_password(
        self, mock_settings, config_file: Path
    ) -> None:
        """Test ShadowRocket subscription generation with custom password."""
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        proxy_config = ProxyConfig(str(config_file))
        custom_password = "custom-password-123"
        subscription_b64 = proxy_config.generate_shadowrocket_subscription(
            password=custom_password
        )

        # Decode base64 to check content
        subscription_content = base64.b64decode(subscription_b64).decode()
        urls = subscription_content.strip().split("\n")

        # Check Hysteria2 URL uses custom password
        hy2_urls = [url for url in urls if url.startswith("hysteria2://")]
        assert len(hy2_urls) == 1
        hy2_url = hy2_urls[0]

        # Extract password from URL
        password_part = hy2_url.split("hysteria2://")[1].split("@")[0]
        assert password_part == custom_password

    @patch("src.proxy_config.settings")
    def test_generate_hysteria2_url(self, mock_settings, config_file: Path) -> None:
        """Test Hysteria2 URL generation."""
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_port = 47012

        proxy_config = ProxyConfig(str(config_file))
        config = {
            "name": "test_proxy",
            "type": "hysteria2",
            "server": "test.host.com",
            "port": 47012,
            "password": "test-password",
            "obfs-password": "test-obfs-password",
        }

        url = proxy_config._generate_hysteria2_url(config)

        expected_url = (
            "hysteria2://test-password@test.host.com:47012?"
            "peer=i.am.com&insecure=1&alpn=h3&obfs=salamander&"
            "obfs-password=test-obfs-password&udp=1#test_proxy.hy2"
        )

        assert url == expected_url

    @patch("src.proxy_config.settings")
    def test_generate_vmess_url(self, mock_settings, config_file: Path) -> None:
        """Test VMess URL generation."""
        proxy_config = ProxyConfig(str(config_file))
        config = {
            "name": "test_proxy",
            "type": "vmess",
            "server": "test.host.com",
            "port": 8080,
            "uuid": "12345678-1234-1234-1234-123456789abc",
        }

        url = proxy_config._generate_vmess_url(config)

        # Check URL format
        assert url.startswith("vmess://")
        assert url.endswith("?fragment=1,40-60,30-50")

        # Decode and check VMess config
        vmess_b64 = url.split("vmess://")[1].split("?")[0]
        vmess_config = json.loads(base64.b64decode(vmess_b64).decode())

        assert vmess_config["v"] == "2"
        assert vmess_config["ps"] == "test_proxy"
        assert vmess_config["add"] == "test.host.com"
        assert vmess_config["port"] == "8080"
        assert vmess_config["id"] == "12345678-1234-1234-1234-123456789abc"
        assert vmess_config["net"] == "ws"
        assert vmess_config["tls"] == "tls"

    @patch("src.proxy_config.settings")
    def test_generate_vless_url(self, mock_settings, config_file: Path) -> None:
        """Test VLESS URL generation."""
        proxy_config = ProxyConfig(str(config_file))
        config = {
            "name": "test_proxy",
            "type": "vless",
            "server": "test.host.com",
            "port": 8080,
            "uuid": "12345678-1234-1234-1234-123456789abc",
        }

        url = proxy_config._generate_vless_url(config)

        # Parse URL
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)

        assert parsed.scheme == "vless"
        assert parsed.username == "12345678-1234-1234-1234-123456789abc"
        assert parsed.hostname == "test.host.com"
        assert parsed.port == 8080
        assert parsed.fragment == "test_proxy"

        # Check query parameters
        assert query_params["type"] == ["ws"]
        assert query_params["path"] == ["/ws"]
        assert query_params["security"] == ["tls"]

    @patch("src.proxy_config.settings")
    def test_generate_shadowrocket_subscription_v2(
        self, mock_settings, config_file: Path
    ) -> None:
        """Test ShadowRocket subscription generation for v2 subscription."""
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_v2_port = 47013

        proxy_config = ProxyConfig(str(config_file))
        subscription_b64 = proxy_config.generate_shadowrocket_subscription("v2", "test-password", "testuser")

        # Decode base64 to check content
        subscription_content = base64.b64decode(subscription_b64).decode()
        urls = subscription_content.strip().split("\n")

        # Should have 1 URL (one per proxy)
        assert len(urls) == 1

        # Check Hysteria2 v2 URL
        hy2_urls = [url for url in urls if url.startswith("hysteria2://")]
        assert len(hy2_urls) == 1
        hy2_url = hy2_urls[0]

        # Parse Hysteria2 v2 URL
        assert "de-1.contabo.v.dimonb.com:47013" in hy2_url
        assert "peer=i.am.com" in hy2_url
        assert "obfs-password=test-obfs-password" in hy2_url
        assert "#de_1_contabo_v2.hy2" in hy2_url
        # Check that password is in user:password format
        assert "testuser:test-password@" in hy2_url

    @patch("src.proxy_config.settings")
    def test_generate_hysteria2_v2_url(self, mock_settings, config_file: Path) -> None:
        """Test Hysteria2 v2 URL generation."""
        mock_settings.obfs_password = "test-obfs-password"
        mock_settings.hysteria2_v2_port = 47013

        proxy_config = ProxyConfig(str(config_file))
        config = {
            "name": "test_proxy",
            "type": "hysteria2",
            "server": "test.host.com",
            "port": 47013,
            "password": "test-password",
            "obfs-password": "test-obfs-password",
        }

        url = proxy_config._generate_hysteria2_v2_url(config, "user:password")

        expected_url = (
            "hysteria2://user:password@test.host.com:47013?"
            "peer=i.am.com&insecure=1&alpn=h3&obfs=salamander&"
            "obfs-password=test-obfs-password&udp=1#test_proxy.hy2"
        )

        assert url == expected_url
