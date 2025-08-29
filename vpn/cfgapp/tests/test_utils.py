"""Tests for utils module."""

import pytest
from unittest.mock import AsyncMock, patch
from src.utils import (
    IPProcessor,
    TemplateProcessor,
    ipv4_cover_blocks,
    ipv6_cidr_to_blocks,
    dedupe_lines,
    netset_expand,
)


class TestIPProcessor:
    """Test IPProcessor class."""

    def test_ipv4_cover_blocks_single_block(self) -> None:
        """Test IPv4 cover blocks when original fits in single target block."""
        processor = IPProcessor(ipv4_block_prefix=18)
        result = processor.ipv4_cover_blocks("192.168.1.0/24")
        assert result == ["192.168.0.0/18"]

    def test_ipv4_cover_blocks_multiple_blocks(self) -> None:
        """Test IPv4 cover blocks when original spans multiple target blocks."""
        processor = IPProcessor(ipv4_block_prefix=18)
        result = processor.ipv4_cover_blocks("192.168.0.0/16")
        expected = [
            "192.168.0.0/18",
            "192.168.64.0/18",
            "192.168.128.0/18",
            "192.168.192.0/18",
        ]
        assert result == expected

    def test_ipv4_cover_blocks_already_larger(self) -> None:
        """Test IPv4 cover blocks when original is already larger than target."""
        processor = IPProcessor(ipv4_block_prefix=18)
        result = processor.ipv4_cover_blocks("192.168.0.0/16")
        # Should return multiple /18 blocks covering the /16
        assert len(result) == 4
        assert all("/18" in block for block in result)

    def test_ipv6_cidr_to_blocks_single_block(self) -> None:
        """Test IPv6 CIDR to blocks when original fits in single target block."""
        processor = IPProcessor(ipv6_block_prefix=32)
        result = processor.ipv6_cidr_to_blocks("2001:db8::/48")
        assert result == ["2001:db8::/32"]

    def test_ipv6_cidr_to_blocks_already_larger(self) -> None:
        """Test IPv6 CIDR to blocks when original is already larger than target."""
        processor = IPProcessor(ipv6_block_prefix=32)
        result = processor.ipv6_cidr_to_blocks("2001:db8::/32")
        assert result == ["2001:db8::/32"]

    def test_netset_expand_ipv4(self) -> None:
        """Test netset expansion with IPv4 CIDR."""
        processor = IPProcessor(ipv4_block_prefix=18)
        text = "192.168.1.0/24"
        suffix = ",PROXY,no-resolve"
        result = processor.netset_expand(text, suffix)
        assert result == ["IP-CIDR,192.168.0.0/18,PROXY,no-resolve"]

    def test_netset_expand_ipv6(self) -> None:
        """Test netset expansion with IPv6 CIDR."""
        processor = IPProcessor(ipv6_block_prefix=32)
        text = "2001:db8::/48"
        suffix = ",PROXY,no-resolve"
        result = processor.netset_expand(text, suffix)
        assert result == ["IP-CIDR,2001:db8::/32,PROXY,no-resolve"]

    def test_netset_expand_with_comments(self) -> None:
        """Test netset expansion with comments and empty lines."""
        processor = IPProcessor(ipv4_block_prefix=18)
        text = """
# This is a comment
192.168.1.0/24
; Another comment

10.0.0.0/24
"""
        suffix = ",PROXY,no-resolve"
        result = processor.netset_expand(text, suffix)
        expected = [
            "IP-CIDR,192.168.0.0/18,PROXY,no-resolve",
            "IP-CIDR,10.0.0.0/18,PROXY,no-resolve",
        ]
        assert result == expected

    def test_netset_expand_with_ip_prefix(self) -> None:
        """Test netset expansion with 'IP ' prefix."""
        processor = IPProcessor(ipv4_block_prefix=18)
        text = "IP 192.168.1.0/24"
        suffix = ",PROXY,no-resolve"
        result = processor.netset_expand(text, suffix)
        assert result == ["IP-CIDR,192.168.0.0/18,PROXY,no-resolve"]

    def test_dedupe_lines(self) -> None:
        """Test line deduplication."""
        processor = IPProcessor()
        lines = ["a", "b", "a", "c", "b"]
        result = processor.dedupe_lines(lines)
        assert result == ["a", "b", "c"]

    def test_dedupe_lines_preserves_order(self) -> None:
        """Test line deduplication preserves order."""
        processor = IPProcessor()
        lines = ["b", "a", "c", "a", "b"]
        result = processor.dedupe_lines(lines)
        assert result == ["b", "a", "c"]


class TestTemplateProcessor:
    """Test TemplateProcessor class."""

    def test_parse_template_no_rulesets(self) -> None:
        """Test template parsing with no RULE-SET entries."""
        ip_processor = IPProcessor()
        processor = TemplateProcessor(ip_processor)
        text = "DOMAIN,example.com,PROXY\nDOMAIN-SUFFIX,test.com,DIRECT"
        result = processor.parse_template(text)
        assert result["tasks"] == []
        assert result["original_line_count"] == 2
        assert result["passthrough"][0] == "DOMAIN,example.com,PROXY"
        assert result["passthrough"][1] == "DOMAIN-SUFFIX,test.com,DIRECT"

    def test_parse_template_with_rulesets(self) -> None:
        """Test template parsing with RULE-SET entries."""
        ip_processor = IPProcessor()
        processor = TemplateProcessor(ip_processor)
        text = """
DOMAIN,example.com,PROXY
RULE-SET,https://example.com/rules.txt,PROXY,no-resolve
DOMAIN-SUFFIX,test.com,DIRECT
"""
        result = processor.parse_template(text)
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["url"] == "https://example.com/rules.txt"
        assert result["tasks"][0]["suffix"] == ",PROXY,no-resolve"
        assert result["original_line_count"] == 5  # Including empty lines

    @pytest.mark.asyncio
    async def test_expand_netset_success(self) -> None:
        """Test NETSET expansion with successful fetch."""
        ip_processor = IPProcessor(ipv4_block_prefix=18)
        processor = TemplateProcessor(ip_processor)
        
        # Create a mock response that behaves like aiohttp.ClientResponse
        mock_response = AsyncMock()
        mock_response.ok = True
        mock_response.text = AsyncMock(return_value="192.168.1.0/24")
        
        # Create a mock session that returns the mock response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        result = await processor.expand_netset(
            "https://example.com/netset.txt", ",PROXY,no-resolve", mock_session
        )
        assert result == ["IP-CIDR,192.168.0.0/18,PROXY,no-resolve"]

    @pytest.mark.asyncio
    async def test_expand_netset_failure(self) -> None:
        """Test NETSET expansion with failed fetch."""
        ip_processor = IPProcessor()
        processor = TemplateProcessor(ip_processor)
        
        mock_response = AsyncMock()
        mock_response.ok = False
        mock_response.status = 404
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        result = await processor.expand_netset(
            "https://example.com/netset.txt", ",PROXY,no-resolve", mock_session
        )
        assert result == ["# NETSET fetch failed: https://example.com/netset.txt (404)"]

    @pytest.mark.asyncio
    async def test_expand_rule_set_with_netsets(self) -> None:
        """Test RULE-SET expansion with NETSET entries."""
        ip_processor = IPProcessor(ipv4_block_prefix=18)
        processor = TemplateProcessor(ip_processor)
        
        mock_response = AsyncMock()
        mock_response.ok = True
        mock_response.text = AsyncMock(return_value="#NETSET https://example.com/netset.txt")
        
        mock_netset_response = AsyncMock()
        mock_netset_response.ok = True
        mock_netset_response.text = AsyncMock(return_value="192.168.1.0/24")
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_response, mock_netset_response])
        
        task = {"url": "https://example.com/rules.txt", "suffix": ",PROXY,no-resolve"}
        result = await processor.expand_rule_set(task, mock_session)
        
        assert result[0] == "# RULE-SET,https://example.com/rules.txt"
        assert "IP-CIDR,192.168.0.0/18,PROXY,no-resolve" in result

    @pytest.mark.asyncio
    async def test_expand_rule_set_regular_rules(self) -> None:
        """Test RULE-SET expansion with regular rules."""
        ip_processor = IPProcessor()
        processor = TemplateProcessor(ip_processor)
        
        mock_response = AsyncMock()
        mock_response.ok = True
        mock_response.text = AsyncMock(return_value="""
DOMAIN,example.com,PROXY
DOMAIN-SUFFIX,test.com,DIRECT
""")
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        task = {"url": "https://example.com/rules.txt", "suffix": ",PROXY,no-resolve"}
        result = await processor.expand_rule_set(task, mock_session)
        
        assert result[0] == "# RULE-SET,https://example.com/rules.txt"
        assert "DOMAIN,example.com,PROXY,no-resolve" in result
        assert "DOMAIN-SUFFIX,test.com,PROXY,no-resolve" in result

    @pytest.mark.asyncio
    async def test_process_template(self) -> None:
        """Test full template processing."""
        ip_processor = IPProcessor(ipv4_block_prefix=18)
        processor = TemplateProcessor(ip_processor)
        
        template_text = """
DOMAIN,example.com,PROXY
RULE-SET,https://example.com/rules.txt,PROXY,no-resolve
DOMAIN-SUFFIX,test.com,DIRECT
"""
        
        # Mock the RULE-SET response
        mock_response = AsyncMock()
        mock_response.ok = True
        mock_response.text = AsyncMock(return_value="192.168.1.0/24")
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await processor.process_template(template_text)
            
            assert "DOMAIN,example.com,PROXY" in result
            assert "192.168.1.0/24,PROXY,no-resolve" in result
            assert "DOMAIN-SUFFIX,test.com,DIRECT" in result


class TestConvenienceFunctions:
    """Test convenience functions for backward compatibility."""

    def test_ipv4_cover_blocks_function(self) -> None:
        """Test ipv4_cover_blocks convenience function."""
        result = ipv4_cover_blocks("192.168.1.0/24", 18)
        assert result == ["192.168.0.0/18"]

    def test_ipv6_cidr_to_blocks_function(self) -> None:
        """Test ipv6_cidr_to_blocks convenience function."""
        result = ipv6_cidr_to_blocks("2001:db8::/48", 32)
        assert result == ["2001:db8::/32"]

    def test_dedupe_lines_function(self) -> None:
        """Test dedupe_lines convenience function."""
        lines = ["a", "b", "a", "c"]
        result = dedupe_lines(lines)
        assert result == ["a", "b", "c"]

    def test_netset_expand_function(self) -> None:
        """Test netset_expand convenience function."""
        text = "192.168.1.0/24"
        suffix = ",PROXY,no-resolve"
        result = netset_expand(text, suffix, 18, 32)
        assert result == ["IP-CIDR,192.168.0.0/18,PROXY,no-resolve"]
