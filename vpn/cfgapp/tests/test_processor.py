"""Tests for template processor."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.processor import NETSET_RE, RULE_RE, TemplateProcessor


class TestTemplateProcessor:
    """Test TemplateProcessor class."""

    @pytest.fixture
    def http_client(self) -> AsyncMock:
        """Create mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def processor(self, http_client: AsyncMock) -> TemplateProcessor:
        """Create TemplateProcessor instance."""
        return TemplateProcessor(http_client)

    def test_parse_template(self, processor: TemplateProcessor) -> None:
        """Test template parsing."""
        template_text = """
# Comment line
RULE-SET,https://example.com/list.txt,PROXY
# Another comment
RULE-SET,https://test.com/block.txt,DIRECT,no-resolve
DOMAIN,example.com,PROXY
"""

        tasks, passthrough, line_count = processor.parse_template(template_text)

        assert line_count == 7
        assert len(tasks) == 2

        # Check first task
        assert tasks[0]["url"] == "https://example.com/list.txt"
        assert tasks[0]["suffix"] == ",PROXY"
        assert tasks[0]["index"] == 2

        # Check second task
        assert tasks[1]["url"] == "https://test.com/block.txt"
        assert tasks[1]["suffix"] == ",DIRECT,no-resolve"
        assert tasks[1]["index"] == 4

        # Check passthrough lines
        assert passthrough[0] == ""  # Empty line
        assert passthrough[1] == "# Comment line"
        assert passthrough[3] == "# Another comment"
        assert passthrough[5] == "DOMAIN,example.com,PROXY"

    def test_parse_template_no_rules(self, processor: TemplateProcessor) -> None:
        """Test template parsing with no RULE-SET entries."""
        template_text = """
# Only comments
DOMAIN,example.com,PROXY
IP-CIDR,192.168.1.0/24,DIRECT
"""

        tasks, passthrough, line_count = processor.parse_template(template_text)

        assert line_count == 5
        assert len(tasks) == 0
        assert passthrough[1] == "# Only comments"
        assert passthrough[2] == "DOMAIN,example.com,PROXY"
        assert passthrough[3] == "IP-CIDR,192.168.1.0/24,DIRECT"

    @pytest.mark.asyncio
    async def test_smart_fetch_external(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test smart fetch for external URLs."""
        url = "https://external.com/path"
        incoming_host = "example.com"
        request_headers = {"User-Agent": "test"}

        mock_response = AsyncMock()
        mock_response.text = "external content"
        mock_response.raise_for_status = Mock()
        http_client.get.return_value = mock_response

        result = await processor.smart_fetch(url, incoming_host, request_headers)

        assert result == "external content"
        http_client.get.assert_called_once_with(url)
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_smart_fetch_same_host(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test smart fetch for same host (should proxy via API_HOST)."""
        from src.config import settings

        url = "https://example.com/path"
        incoming_host = "example.com"
        request_headers = {"User-Agent": "test", "cookie": "session=123"}

        mock_response = AsyncMock()
        mock_response.text = "proxied content"
        mock_response.raise_for_status = Mock()
        http_client.get.return_value = mock_response

        result = await processor.smart_fetch(url, incoming_host, request_headers)

        assert result == "proxied content"

        # Should call with API_HOST
        expected_url = f"https://{settings.api_host}/path"
        http_client.get.assert_called_once()
        call_args = http_client.get.call_args
        assert call_args[0][0] == expected_url

        # Should remove cookie header
        headers = call_args[1]["headers"]
        assert "cookie" not in headers
        assert headers["User-Agent"] == "test"
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_netset_success(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test successful NETSET expansion."""
        url = "https://example.com/netset.txt"
        suffix = ",PROXY"

        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.text = "192.168.1.0/24\n10.0.0.0/8"
        http_client.get.return_value = mock_response

        result = await processor.expand_netset(url, suffix)

        assert len(result) > 0
        assert any("IP-CIDR,192.168.0.0/18" in line for line in result)
        assert any("IP-CIDR,10.0.0.0/18" in line for line in result)

    @pytest.mark.asyncio
    async def test_expand_netset_failure(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test NETSET expansion failure."""
        url = "https://example.com/netset.txt"
        suffix = ",PROXY"

        mock_response = AsyncMock()
        mock_response.is_success = False
        mock_response.status_code = 404
        http_client.get.return_value = mock_response

        result = await processor.expand_netset(url, suffix)

        assert len(result) == 1
        assert result[0] == f"# NETSET fetch failed: {url} (404)"

    @pytest.mark.asyncio
    async def test_expand_rule_set_with_netset(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test RULE-SET expansion with NETSET entries."""
        task = {"url": "https://example.com/rules.txt", "suffix": ",PROXY"}
        incoming_host = "example.com"
        request_headers = {"User-Agent": "test"}

        # Mock the rule list response
        rule_response = AsyncMock()
        rule_response.text = (
            "#NETSET https://example.com/netset.txt\n#NETSET https://test.com/block.txt"
        )
        rule_response.raise_for_status = Mock()

        # Mock NETSET responses
        netset_response = AsyncMock()
        netset_response.text = "192.168.1.0/24"
        netset_response.is_success = True

        http_client.get.side_effect = [rule_response, netset_response, netset_response]

        result = await processor.expand_rule_set(task, incoming_host, request_headers)

        assert len(result) > 1
        assert result[0] == f"# RULE-SET,{task['url']}"
        assert any("IP-CIDR,192.168.0.0/18" in line for line in result)

    @pytest.mark.asyncio
    async def test_expand_rule_set_regular_rules(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test RULE-SET expansion with regular rules."""
        task = {"url": "https://example.com/rules.txt", "suffix": ",PROXY"}
        incoming_host = "example.com"
        request_headers = {"User-Agent": "test"}

        # Mock the rule list response
        rule_response = AsyncMock()
        rule_response.text = """
DOMAIN,example.com,PROXY
DOMAIN-SUFFIX,test.com,DIRECT
IP-CIDR,192.168.1.0/24,DIRECT
"""
        rule_response.raise_for_status = Mock()

        http_client.get.return_value = rule_response

        result = await processor.expand_rule_set(task, incoming_host, request_headers)

        assert len(result) == 4  # Header + 3 rules
        assert result[0] == f"# RULE-SET,{task['url']}"
        assert "DOMAIN,example.com,PROXY" in result
        assert "DOMAIN-SUFFIX,test.com,PROXY" in result  # Suffix replaced
        assert "IP-CIDR,192.168.1.0/24,PROXY" in result  # Suffix added

    @pytest.mark.asyncio
    async def test_process_template(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Test full template processing."""
        template_text = """
# Template with rules
RULE-SET,https://example.com/rules.txt,PROXY
# More content
DOMAIN,example.com,PROXY
"""
        incoming_host = "example.com"
        request_headers = {"User-Agent": "test"}

        # Mock responses
        rule_response = AsyncMock()
        rule_response.text = "DOMAIN,test.com,PROXY"
        rule_response.raise_for_status = Mock()

        http_client.get.return_value = rule_response

        result = await processor.process_template(
            template_text, incoming_host, request_headers
        )

        assert "# Template with rules" in result
        assert "DOMAIN,test.com,PROXY" in result
        assert "DOMAIN,example.com,PROXY" in result


class TestRegexPatterns:
    """Test regex patterns for parsing."""

    def test_rule_set_pattern(self) -> None:
        """Test RULE-SET regex pattern."""
        valid_cases = [
            "RULE-SET,https://example.com/list.txt,PROXY",
            "RULE-SET,https://test.com/block.txt,DIRECT,no-resolve",
            "RULE-SET,http://local.com/rules.txt,REJECT",
            "  RULE-SET,https://example.com/list.txt,PROXY  ",
            "RULE-SET,https://example.com/list.txt,PROXY # comment",
        ]

        invalid_cases = [
            "RULE-SET",
            "RULE-SET,https://example.com/list.txt",
            "RULE-SET,https://example.com/list.txt,",
        ]

        for case in valid_cases:
            assert RULE_RE.match(case) is not None, f"Should match: {case}"

        for case in invalid_cases:
            assert RULE_RE.match(case) is None, f"Should not match: {case}"

    def test_netset_pattern(self) -> None:
        """Test NETSET regex pattern."""
        valid_cases = [
            "#NETSET https://example.com/netset.txt",
            "#NETSET http://test.com/block.txt",
            "#NETSET https://example.com/netset.txt # comment",
        ]

        invalid_cases = [
            "NETSET https://example.com/netset.txt",
            "#NETSET",
            "#NETSET ",
            "NETSET https://example.com/netset.txt",
        ]

        for case in valid_cases:
            assert NETSET_RE.match(case) is not None, f"Should match: {case}"

        for case in invalid_cases:
            assert NETSET_RE.match(case) is None, f"Should not match: {case}"
