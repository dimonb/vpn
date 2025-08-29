"""Tests for utility functions."""

import pytest
from src.utils import (
    ip_to_int,
    int_to_ip,
    cidr_range_v4,
    ipv4_cover_blocks,
    dedupe_lines,
    netset_expand,
    RE_IPV4_CIDR,
    RE_IPV6_CIDR
)


class TestIPUtils:
    """Test IP utility functions."""

    def test_ip_to_int(self) -> None:
        """Test IP to integer conversion."""
        assert ip_to_int("192.168.1.1") == 3232235777
        assert ip_to_int("10.0.0.1") == 167772161
        assert ip_to_int("127.0.0.1") == 2130706433

    def test_int_to_ip(self) -> None:
        """Test integer to IP conversion."""
        assert int_to_ip(3232235777) == "192.168.1.1"
        assert int_to_ip(167772161) == "10.0.0.1"
        assert int_to_ip(2130706433) == "127.0.0.1"

    def test_cidr_range_v4(self) -> None:
        """Test CIDR range calculation for IPv4."""
        start, end = cidr_range_v4("192.168.1.0/24")
        assert start == 3232235776  # 192.168.1.0
        assert end == 3232236031    # 192.168.1.255

    def test_ipv4_cover_blocks(self) -> None:
        """Test IPv4 cover blocks generation."""
        blocks = ipv4_cover_blocks("192.168.1.0/24", 18)
        assert len(blocks) == 4
        assert "192.168.0.0/18" in blocks
        assert "192.168.64.0/18" in blocks


class TestRegexPatterns:
    """Test regex patterns for IP validation."""

    def test_ipv4_cidr_pattern(self) -> None:
        """Test IPv4 CIDR regex pattern."""
        valid_cases = [
            "192.168.1.0/24",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "0.0.0.0/0"
        ]
        
        invalid_cases = [
            "192.168.1.0",
            "192.168.1.0/33",
            "192.168.1.0/",
            "192.168.1/24",
            "192.168.1.0.1/24"
        ]
        
        for case in valid_cases:
            assert RE_IPV4_CIDR.match(case) is not None, f"Should match: {case}"
        
        for case in invalid_cases:
            assert RE_IPV4_CIDR.match(case) is None, f"Should not match: {case}"

    def test_ipv6_cidr_pattern(self) -> None:
        """Test IPv6 CIDR regex pattern."""
        valid_cases = [
            "2001:db8::/32",
            "::/0",
            "2001:db8:1::/48",
            "2001:db8:1:2::/64"
        ]
        
        invalid_cases = [
            "2001:db8::",
            "2001:db8::/",
            "2001:db8::/129",
            "2001:db8/32"
        ]
        
        for case in valid_cases:
            assert RE_IPV6_CIDR.match(case) is not None, f"Should match: {case}"
        
        for case in invalid_cases:
            assert RE_IPV6_CIDR.match(case) is None, f"Should not match: {case}"


class TestDeduplication:
    """Test line deduplication."""

    def test_dedupe_lines(self) -> None:
        """Test line deduplication functionality."""
        input_lines = [
            "line1",
            "line2",
            "line1",  # duplicate
            "line3",
            "line2",  # duplicate
            "  line1  ",  # duplicate with whitespace
        ]
        
        expected = ["line1", "line2", "line3"]
        result = dedupe_lines(input_lines)
        
        assert result == expected

    def test_dedupe_lines_empty(self) -> None:
        """Test deduplication with empty input."""
        assert dedupe_lines([]) == []
        assert dedupe_lines(["", "  ", ""]) == []


class TestNetsetExpand:
    """Test NETSET expansion functionality."""

    def test_netset_expand_ipv4(self) -> None:
        """Test IPv4 expansion in NETSET."""
        netset_content = """
# Comment line
192.168.1.0/24
10.0.0.0/8
; Another comment
172.16.0.0/12
"""
        suffix = ",PROXY"
        result = netset_expand(netset_content, suffix)
        
        # Should contain expanded IPv4 blocks
        assert any("IP-CIDR,192.168.0.0/18" in line for line in result)
        assert any("IP-CIDR,10.0.0.0/18" in line for line in result)
        assert any("IP-CIDR,172.16.0.0/18" in line for line in result)
        
        # Should not contain comments
        assert not any(line.startswith("#") for line in result if line.strip())

    def test_netset_expand_with_ip_prefix(self) -> None:
        """Test NETSET expansion with IP prefix."""
        netset_content = """
IP 192.168.1.0/24
IP 10.0.0.0/8
"""
        suffix = ",DIRECT"
        result = netset_expand(netset_content, suffix)
        
        # Should remove IP prefix and expand
        assert any("IP-CIDR,192.168.0.0/18" in line for line in result)
        assert any("IP-CIDR,10.0.0.0/18" in line for line in result)

    def test_netset_expand_empty(self) -> None:
        """Test NETSET expansion with empty content."""
        result = netset_expand("", ",PROXY")
        assert result == []
        
        result = netset_expand("# Only comments\n; More comments", ",PROXY")
        assert result == []
