"""Tests for proxy configuration module."""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from src.proxy_config import ProxyConfig


class TestProxyConfig:
    """Test cases for ProxyConfig class."""

    @pytest.fixture
    def sample_config(self) -> Dict[str, Any]:
        """Sample configuration for testing."""
        return {
            "users": ["dimonb", "diakon", "ivan", "petrov"],
            "subs": {
                "default": {
                    "DE_1_CONTABO": {"protocol": "hy2", "host": "de-1.contabo.v.dimonb.com"},
                    "US_1_VULTR": {"protocol": "vmess", "host": "us-1.vultr.v.dimonb.com"}
                }
            }
        }

    @pytest.fixture
    def config_file(self, sample_config: Dict[str, Any]) -> Path:
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_config, f)
            return Path(f.name)

    def test_load_config_success(self, config_file: Path, sample_config: Dict[str, Any]) -> None:
        """Test successful config loading."""
        proxy_config = ProxyConfig(str(config_file))
        assert proxy_config.config_data == sample_config

    def test_load_config_file_not_found(self) -> None:
        """Test config loading with non-existent file."""
        with pytest.raises(FileNotFoundError):
            ProxyConfig("/non/existent/path.json")

    def test_load_config_invalid_json(self) -> None:
        """Test config loading with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            config_path = Path(f.name)

        try:
            with pytest.raises(json.JSONDecodeError):
                ProxyConfig(str(config_path))
        finally:
            config_path.unlink()

    def test_get_users(self, config_file: Path) -> None:
        """Test getting users list."""
        proxy_config = ProxyConfig(str(config_file))
        users = proxy_config.get_users()
        assert users == ["dimonb", "diakon", "ivan", "petrov"]

    def test_get_subs(self, config_file: Path) -> None:
        """Test getting subscriptions."""
        proxy_config = ProxyConfig(str(config_file))
        subs = proxy_config.get_subs()
        assert "default" in subs
        assert "DE_1_CONTABO" in subs["default"]
        assert "US_1_VULTR" in subs["default"]

    def test_generate_proxy_configs(self, config_file: Path) -> None:
        """Test proxy configuration generation."""
        proxy_config = ProxyConfig(str(config_file))
        configs = proxy_config.generate_proxy_configs()
        
        # Should generate configs for 2 proxies * 4 users = 8 configs
        assert len(configs) == 8
        
        # Check that all configs have required fields
        for config in configs:
            assert "name" in config
            assert "type" in config
            assert "server" in config
            assert "port" in config

    def test_generate_hysteria2_config(self, config_file: Path) -> None:
        """Test Hysteria2 configuration generation."""
        proxy_config = ProxyConfig(str(config_file))
        config = proxy_config._generate_hysteria2_config(
            "test.host.com", "testuser", "TEST_PROXY"
        )
        
        assert config["type"] == "hysteria2"
        assert config["server"] == "test.host.com"
        assert config["name"] == "test_proxy-testuser"
        assert "password" in config
        assert "port" in config
        assert config["skip-cert-verify"] is True
        assert config["alpn"] == ["h3"]
        assert config["obfs"] == "salamander"

    def test_generate_vmess_config(self, config_file: Path) -> None:
        """Test VMess configuration generation."""
        proxy_config = ProxyConfig(str(config_file))
        config = proxy_config._generate_vmess_config(
            "test.host.com", "testuser", "TEST_PROXY"
        )
        
        assert config["type"] == "vmess"
        assert config["server"] == "test.host.com"
        assert config["name"] == "test_proxy-testuser"
        assert "uuid" in config
        assert "port" in config
        assert config["tls"] is True
        assert config["cipher"] == "auto"

    def test_generate_vless_config(self, config_file: Path) -> None:
        """Test VLESS configuration generation."""
        proxy_config = ProxyConfig(str(config_file))
        config = proxy_config._generate_vless_config(
            "test.host.com", "testuser", "TEST_PROXY"
        )
        
        assert config["type"] == "vless"
        assert config["server"] == "test.host.com"
        assert config["name"] == "test_proxy-testuser"
        assert "uuid" in config
        assert "port" in config
        assert config["tls"] is True
        assert config["network"] == "ws"

    def test_get_proxy_list(self, config_file: Path) -> None:
        """Test getting proxy list."""
        proxy_config = ProxyConfig(str(config_file))
        proxy_list = proxy_config.get_proxy_list()
        
        # Should have 8 proxy names (2 proxies * 4 users)
        assert len(proxy_list) == 8
        
        # Check that names follow expected pattern
        expected_names = [
            "de_1_contabo-dimonb", "de_1_contabo-diakon", "de_1_contabo-ivan", "de_1_contabo-petrov",
            "us_1_vultr-dimonb", "us_1_vultr-diakon", "us_1_vultr-ivan", "us_1_vultr-petrov"
        ]
        assert set(proxy_list) == set(expected_names)

    def test_unsupported_protocol(self, config_file: Path) -> None:
        """Test handling of unsupported protocols."""
        proxy_config = ProxyConfig(str(config_file))
        config = proxy_config._generate_proxy_config("unsupported", "test.host.com", "testuser", "TEST")
        assert config == {}

    def test_password_generation_consistency(self, config_file: Path) -> None:
        """Test that password generation is consistent."""
        proxy_config = ProxyConfig(str(config_file))
        
        # Same input should produce same output
        password1 = proxy_config._generate_password("user1", "proxy1")
        password2 = proxy_config._generate_password("user1", "proxy1")
        assert password1 == password2
        
        # Different input should produce different output
        password3 = proxy_config._generate_password("user2", "proxy1")
        assert password1 != password3

    def test_port_generation_range(self, config_file: Path) -> None:
        """Test that port generation is within expected range."""
        proxy_config = ProxyConfig(str(config_file))
        
        for _ in range(100):
            port = proxy_config._generate_port("testuser", "testproxy")
            assert 40000 <= port <= 49999

    def test_uuid_generation_format(self, config_file: Path) -> None:
        """Test that UUID generation produces valid UUID format."""
        import uuid
        
        proxy_config = ProxyConfig(str(config_file))
        
        for _ in range(10):
            generated_uuid = proxy_config._generate_uuid("testuser", "testproxy")
            # Should be valid UUID format
            uuid.UUID(generated_uuid)
