"""Tests for CLASH processor module."""

from unittest.mock import AsyncMock

import pytest

from src.clash_processor import ClashProcessor
from src.processor import TemplateProcessor
from src.utils import IPProcessor


class TestClashProcessor:
    """Test CLASH processor functions."""

    @pytest.fixture
    def ip_processor(self) -> IPProcessor:
        """Create IP processor fixture."""
        return IPProcessor(ipv4_block_prefix=18, ipv6_block_prefix=32)

    @pytest.fixture
    def template_processor(self, ip_processor: IPProcessor) -> TemplateProcessor:
        """Create template processor fixture."""
        return TemplateProcessor(ip_processor)

    @pytest.fixture
    def clash_processor(self, template_processor: TemplateProcessor) -> ClashProcessor:
        """Create CLASH processor fixture."""
        return ClashProcessor(template_processor)

    def test_parse_clash_yaml(self, clash_processor: ClashProcessor) -> None:
        """Test parsing CLASH YAML."""
        yaml_content = """
mixed-port: 7890
allow-lan: true
mode: Rule
log-level: info
"""
        result = clash_processor.parse_clash_yaml(yaml_content)
        assert result["mixed-port"] == 7890
        assert result["allow-lan"] is True
        assert result["mode"] == "Rule"

    def test_extract_rule_sets(self, clash_processor: ClashProcessor) -> None:
        """Test extracting RULE-SET entries."""
        clash_config = {
            "rules": [
                "DOMAIN-SUFFIX,example.com,PROXY",
                "RULE-SET,https://example.com/list.txt,PROXY",
                "DOMAIN-SUFFIX,test.com,DIRECT"
            ]
        }

        result = clash_processor.extract_rule_sets(clash_config)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/list.txt"
        assert result[0]["proxy_group"] == "PROXY"

    def test_extract_rule_sets_no_rules(self, clash_processor: ClashProcessor) -> None:
        """Test extracting RULE-SET entries when no rules exist."""
        clash_config = {"mixed-port": 7890}
        result = clash_processor.extract_rule_sets(clash_config)
        assert result == []

    @pytest.mark.asyncio
    async def test_process_clash_config_no_rule_sets(self, clash_processor: ClashProcessor) -> None:
        """Test processing CLASH config without RULE-SET entries."""
        yaml_content = """
mixed-port: 7890
allow-lan: true
mode: Rule
rules:
  - DOMAIN-SUFFIX,example.com,PROXY
"""
        result = await clash_processor.process_clash_config(yaml_content, "", {})
        assert "DOMAIN-SUFFIX,example.com,PROXY" in result

    @pytest.mark.asyncio
    async def test_process_clash_config_with_rule_sets(self, clash_processor: ClashProcessor) -> None:
        """Test processing CLASH config with RULE-SET entries."""
        # Mock the template processor to return expanded rules
        clash_processor.template_processor.process_template = AsyncMock(
            return_value="# RULE-SET,https://example.com/list.txt\nDOMAIN-SUFFIX,test.com,PROXY"
        )

        yaml_content = """
mixed-port: 7890
rules:
  - RULE-SET,https://example.com/list.txt,PROXY
  - DOMAIN-SUFFIX,example.com,PROXY
"""
        result = await clash_processor.process_clash_config(yaml_content, "", {})

        # Should contain the expanded rule but not the original RULE-SET
        assert "DOMAIN-SUFFIX,test.com,PROXY" in result
        assert "RULE-SET,https://example.com/list.txt,PROXY" not in result
        assert "DOMAIN-SUFFIX,example.com,PROXY" in result


