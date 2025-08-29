"""Tests for utils module."""

from src.utils import (
    IPProcessor,
    dedupe_lines,
    ipv4_cover_blocks,
    ipv6_cidr_to_blocks,
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
        lines = ["c", "a", "b", "a", "c"]
        result = processor.dedupe_lines(lines)
        assert result == ["c", "a", "b"]


class TestConvenienceFunctions:
    """Test convenience functions."""

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
        suffix = ",PROXY"
        result = netset_expand(text, suffix, 18)
        assert result == ["IP-CIDR,192.168.0.0/18,PROXY"]
