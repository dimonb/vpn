"""Integration tests for ClashProcessor with ProxyConfig."""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock

import pytest
import yaml

from src.clash_processor import ClashProcessor
from src.proxy_config import ProxyConfig
from src.processor import TemplateProcessor


class TestClashProcessorIntegration:
    """Integration tests for ClashProcessor with ProxyConfig."""

    @pytest.fixture
    def sample_config(self) -> Dict[str, Any]:
        """Sample proxy configuration for testing."""
        return {
            "users": ["dimonb", "diakon"],
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

    @pytest.fixture
    def sample_clash_yaml(self) -> str:
        """Sample Clash YAML configuration."""
        return """
mixed-port: 7890
allow-lan: true
mode: Rule
log-level: info

dns:
  enable: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  nameserver:
    - https://1.1.1.1/dns-query
    - https://8.8.8.8/dns-query

proxies:
  - PROXY_CONFIGS

proxy-groups:
  - name: PROXY
    type: url-test
    url: http://www.gstatic.com/generate_204
    interval: 600
    tolerance: 100
    proxies:
      - PROXY_LIST

rules:
  - DOMAIN-SUFFIX,whatismyipaddress.com,PROXY
  - MATCH,DIRECT
"""

    @pytest.fixture
    def mock_template_processor(self) -> TemplateProcessor:
        """Create mock template processor."""
        processor = AsyncMock(spec=TemplateProcessor)
        return processor

    @pytest.fixture
    def proxy_config(self, config_file: Path) -> ProxyConfig:
        """Create ProxyConfig instance."""
        return ProxyConfig(str(config_file))

    @pytest.fixture
    def clash_processor(self, mock_template_processor: TemplateProcessor, 
                       proxy_config: ProxyConfig) -> ClashProcessor:
        """Create ClashProcessor instance with ProxyConfig."""
        return ClashProcessor(mock_template_processor, proxy_config)

    def test_replace_proxy_placeholders(self, clash_processor: ClashProcessor, 
                                      sample_clash_yaml: str) -> None:
        """Test replacement of PROXY_CONFIGS and PROXY_LIST placeholders."""
        # Parse YAML
        clash_config = clash_processor.parse_clash_yaml(sample_clash_yaml)
        
        # Replace placeholders
        updated_config = clash_processor.replace_proxy_placeholders(clash_config)
        
        # Check that PROXY_CONFIGS was replaced
        assert 'proxies' in updated_config
        assert isinstance(updated_config['proxies'], list)
        assert len(updated_config['proxies']) == 4  # 2 proxies * 2 users
        
        # Check that PROXY_LIST was replaced
        assert 'proxy-groups' in updated_config
        proxy_group = updated_config['proxy-groups'][0]
        assert proxy_group['name'] == 'PROXY'
        assert 'proxies' in proxy_group
        assert isinstance(proxy_group['proxies'], list)
        assert len(proxy_group['proxies']) == 4  # 2 proxies * 2 users
        
        # Check proxy names
        expected_names = [
            "de_1_contabo-dimonb", "de_1_contabo-diakon",
            "us_1_vultr-dimonb", "us_1_vultr-diakon"
        ]
        assert set(proxy_group['proxies']) == set(expected_names)

    def test_replace_proxy_placeholders_no_proxy_config(self, mock_template_processor: TemplateProcessor, 
                                                       sample_clash_yaml: str) -> None:
        """Test placeholder replacement when no proxy config is available."""
        clash_processor = ClashProcessor(mock_template_processor, None)
        
        # Parse YAML
        clash_config = clash_processor.parse_clash_yaml(sample_clash_yaml)
        
        # Replace placeholders (should not change anything)
        updated_config = clash_processor.replace_proxy_placeholders(clash_config)
        
        # Should remain unchanged
        assert updated_config == clash_config

    def test_replace_proxy_placeholders_no_placeholders(self, clash_processor: ClashProcessor) -> None:
        """Test placeholder replacement when no placeholders are present."""
        yaml_content = """
mixed-port: 7890
proxies:
  - name: existing-proxy
    type: http
    server: example.com
    port: 8080
proxy-groups:
  - name: PROXY
    type: select
    proxies:
      - existing-proxy
"""
        
        clash_config = clash_processor.parse_clash_yaml(yaml_content)
        updated_config = clash_processor.replace_proxy_placeholders(clash_config)
        
        # Should remain unchanged
        assert updated_config == clash_config

    @pytest.mark.asyncio
    async def test_process_clash_config_with_proxy_placeholders(self, clash_processor: ClashProcessor, 
                                                              sample_clash_yaml: str) -> None:
        """Test full clash config processing with proxy placeholders."""
        # Mock template processor to return empty rules
        clash_processor.template_processor.process_template = AsyncMock(return_value="")
        
        # Process config
        result = await clash_processor.process_clash_config(
            sample_clash_yaml, "test.host.com", {}
        )
        
        # Parse result back to check structure
        parsed_result = yaml.safe_load(result)
        
        # Check that placeholders were replaced
        assert 'proxies' in parsed_result
        assert len(parsed_result['proxies']) == 4
        
        assert 'proxy-groups' in parsed_result
        proxy_group = parsed_result['proxy-groups'][0]
        assert len(proxy_group['proxies']) == 4
        
        # Check that rules section is preserved
        assert 'rules' in parsed_result
        assert len(parsed_result['rules']) == 2

    def test_proxy_config_structure(self, clash_processor: ClashProcessor, 
                                   sample_clash_yaml: str) -> None:
        """Test that generated proxy configs have correct structure."""
        clash_config = clash_processor.parse_clash_yaml(sample_clash_yaml)
        updated_config = clash_processor.replace_proxy_placeholders(clash_config)
        
        # Check Hysteria2 config structure
        hysteria2_configs = [p for p in updated_config['proxies'] if p['type'] == 'hysteria2']
        assert len(hysteria2_configs) == 2  # 1 proxy * 2 users
        
        for config in hysteria2_configs:
            assert 'name' in config
            assert 'server' in config
            assert 'port' in config
            assert 'password' in config
            assert 'sni' in config
            assert config['skip-cert-verify'] is True
            assert config['alpn'] == ['h3']
            assert config['obfs'] == 'salamander'
            assert 'obfs-password' in config
            assert config['fast-open'] is True
            assert config['udp'] is True
        
        # Check VMess config structure
        vmess_configs = [p for p in updated_config['proxies'] if p['type'] == 'vmess']
        assert len(vmess_configs) == 2  # 1 proxy * 2 users
        
        for config in vmess_configs:
            assert 'name' in config
            assert 'server' in config
            assert 'port' in config
            assert 'uuid' in config
            assert config['alterId'] == 0
            assert config['cipher'] == 'auto'
            assert config['tls'] is True
            assert 'servername' in config
            assert config['skip-cert-verify'] is True
            assert config['udp'] is True
