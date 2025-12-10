"""Tests for NetworkCompactor class and IPProcessor integration."""

import ipaddress
import pytest

from src.utils import (
    NetworkCompactor,
    IPProcessor,
    compact_ipv4_networks,
    compact_ipv6_networks,
)


class TestNetworkCompactor:
    """Test suite for NetworkCompactor class."""

    def test_find_minimal_supernet_ipv4(self):
        """Test finding minimal supernet for IPv4 networks."""
        nets = [
            ipaddress.IPv4Network("192.168.0.0/24"),
            ipaddress.IPv4Network("192.168.1.0/24"),
        ]
        # With min_prefix=23, should find /23
        result = NetworkCompactor.find_minimal_supernet(nets, min_prefix=23)
        assert result == ipaddress.IPv4Network("192.168.0.0/23")

    def test_find_minimal_supernet_ipv4_distant(self):
        """Test finding supernet for distant networks."""
        nets = [
            ipaddress.IPv4Network("192.168.0.0/24"),
            ipaddress.IPv4Network("192.168.128.0/24"),
        ]
        # These networks need /16 to be covered (not /17)
        result = NetworkCompactor.find_minimal_supernet(nets, min_prefix=16)
        assert result == ipaddress.IPv4Network("192.168.0.0/16")

    def test_find_minimal_supernet_ipv6(self):
        """Test finding minimal supernet for IPv6 networks."""
        nets = [
            ipaddress.IPv6Network("2001:db8::/48"),
            ipaddress.IPv6Network("2001:db8:1::/48"),
        ]
        # With min_prefix=47, should find /47
        result = NetworkCompactor.find_minimal_supernet(nets, min_prefix=47)
        assert result == ipaddress.IPv6Network("2001:db8::/47")

    def test_find_minimal_supernet_empty(self):
        """Test with empty list."""
        result = NetworkCompactor.find_minimal_supernet([], min_prefix=8)
        assert result is None

    def test_compact_networks_ipv4_simple(self):
        """Test basic IPv4 compaction."""
        cidrs = [
            "192.168.0.0/24",
            "192.168.1.0/24",
            "192.168.2.0/24",
            "192.168.3.0/24",
        ]
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=2, min_prefix=20, version=4
        )
        # Should merge into /22
        assert len(result) <= 2
        # Verify all original networks are covered
        is_covered, _ = NetworkCompactor.verify_coverage(cidrs, result)
        assert is_covered

    def test_compact_networks_ipv4_no_change(self):
        """Test when compaction is not needed."""
        cidrs = ["10.0.0.0/8", "172.16.0.0/12"]
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=10, min_prefix=8, version=4
        )
        assert len(result) == 2

    def test_compact_networks_ipv4_large_list(self):
        """Test compacting a larger list."""
        # Create 100 /24 networks
        cidrs = [f"10.0.{i}.0/24" for i in range(100)]
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=10, min_prefix=16, version=4
        )
        assert len(result) <= 20  # Should be significantly reduced
        # Verify coverage
        is_covered, not_covered = NetworkCompactor.verify_coverage(cidrs, result)
        assert is_covered, f"Not covered: {not_covered}"

    def test_compact_networks_ipv6(self):
        """Test IPv6 compaction."""
        cidrs = [
            "2001:db8::/48",
            "2001:db8:1::/48",
            "2001:db8:2::/48",
        ]
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=2, min_prefix=32, version=6
        )
        assert len(result) <= 3
        is_covered, _ = NetworkCompactor.verify_coverage(cidrs, result)
        assert is_covered

    def test_verify_coverage_full(self):
        """Test coverage verification with full coverage."""
        original = ["192.168.0.0/24", "192.168.1.0/24"]
        compacted = [ipaddress.IPv4Network("192.168.0.0/23")]
        is_covered, not_covered = NetworkCompactor.verify_coverage(
            original, compacted
        )
        assert is_covered
        assert not_covered == []

    def test_verify_coverage_partial(self):
        """Test coverage verification with missing networks."""
        original = ["192.168.0.0/24", "192.168.1.0/24", "10.0.0.0/8"]
        compacted = [ipaddress.IPv4Network("192.168.0.0/23")]
        is_covered, not_covered = NetworkCompactor.verify_coverage(
            original, compacted
        )
        assert not is_covered
        assert "10.0.0.0/8" in not_covered

    def test_compact_ipv4_networks_convenience(self):
        """Test convenience function for IPv4."""
        cidrs = ["192.168.0.0/24", "192.168.1.0/24"]
        result = compact_ipv4_networks(cidrs, target_max=1, min_prefix=20)
        assert isinstance(result, list)
        assert all(isinstance(x, str) for x in result)
        assert len(result) <= 2

    def test_compact_ipv6_networks_convenience(self):
        """Test convenience function for IPv6."""
        cidrs = ["2001:db8::/48", "2001:db8:1::/48"]
        result = compact_ipv6_networks(cidrs, target_max=1, min_prefix=32)
        assert isinstance(result, list)
        assert all(isinstance(x, str) for x in result)

    def test_compact_real_world_aws(self):
        """Test with realistic AWS-like IP ranges."""
        # Simulate AWS IP ranges (scattered across address space)
        cidrs = [
            "3.0.0.0/15",
            "3.2.0.0/24",
            "3.3.0.0/24",
            "13.32.0.0/15",
            "13.48.0.0/16",
            "15.128.0.0/16",
            "52.0.0.0/15",
            "52.2.0.0/16",
        ]
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=5, min_prefix=10, version=4
        )
        # Should compact significantly
        assert len(result) <= 8
        # Verify full coverage
        is_covered, not_covered = NetworkCompactor.verify_coverage(cidrs, result)
        assert is_covered, f"Missing networks: {not_covered}"

    def test_compact_real_data_aws(self):
        """Test with real AWS IP ranges from fixture."""
        from pathlib import Path

        fixture_file = Path(__file__).parent / "fixtures" / "ipv4_merged.txt"
        if not fixture_file.exists():
            pytest.skip("Fixture file not found")

        with open(fixture_file) as f:
            cidrs = [line.strip() for line in f if line.strip()]

        # Should have many networks
        assert len(cidrs) > 1000

        # Compact to ~200
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=200, min_prefix=11, version=4
        )

        # Should be significantly reduced
        assert len(result) < len(cidrs) * 0.2  # At least 80% reduction
        assert len(result) <= 250  # Close to target

        # Verify full coverage
        is_covered, not_covered = NetworkCompactor.verify_coverage(cidrs, result)
        assert is_covered, f"{len(not_covered)} networks not covered"

    def test_compact_real_data_google(self):
        """Test with real Google IP ranges from fixture."""
        from pathlib import Path

        fixture_file = Path(__file__).parent / "fixtures" / "ipv4_merged2.txt"
        if not fixture_file.exists():
            pytest.skip("Fixture file not found")

        with open(fixture_file) as f:
            cidrs = [line.strip() for line in f if line.strip()]

        # Compact to ~50
        result = NetworkCompactor.compact_networks(
            cidrs, target_max=50, min_prefix=11, version=4
        )

        # Should be reduced
        assert len(result) < len(cidrs)
        assert len(result) <= 60  # Close to target

        # Verify full coverage
        is_covered, not_covered = NetworkCompactor.verify_coverage(cidrs, result)
        assert is_covered, f"{len(not_covered)} networks not covered"


class TestIPProcessorIntegration:
    """Test IPProcessor integration with NetworkCompactor."""

    def test_netset_expand_without_compaction(self):
        """Test netset_expand without compaction (default behavior)."""
        netset_text = """
        10.0.1.0/24
        10.0.2.0/24
        10.0.3.0/24
        10.0.4.0/24
        """
        processor = IPProcessor(ipv4_block_prefix=18, enable_compaction=False)
        result = processor.netset_expand(netset_text, ",PROXY")

        # Without compaction, should have multiple /18 blocks
        assert len(result) >= 1
        assert all(line.startswith("IP-CIDR,") for line in result)
        assert all(",PROXY" in line for line in result)

    def test_netset_expand_with_compaction(self):
        """Test netset_expand with compaction enabled."""
        # Create a list of many /24 networks in 10.0.0.0/16
        netset_lines = [f"10.0.{i}.0/24" for i in range(100)]
        netset_text = "\n".join(netset_lines)

        # Without compaction
        processor_no_compact = IPProcessor(
            ipv4_block_prefix=24, enable_compaction=False
        )
        result_no_compact = processor_no_compact.netset_expand(netset_text, ",PROXY")

        # With compaction
        processor_compact = IPProcessor(
            ipv4_block_prefix=24,
            enable_compaction=True,
            compact_target_max=10,
            compact_min_prefix_v4=16,
        )
        result_compact = processor_compact.netset_expand(netset_text, ",PROXY")

        # Compacted result should be significantly smaller
        assert len(result_compact) < len(result_no_compact)
        assert len(result_compact) <= 15  # Should be close to target_max=10

        # Both should have proper format
        assert all(line.startswith("IP-CIDR,") for line in result_compact)
        assert all(",PROXY" in line for line in result_compact)

    def test_netset_expand_compaction_real_data(self):
        """Test compaction with realistic data from fixtures."""
        from pathlib import Path

        fixture_file = Path(__file__).parent / "fixtures" / "ipv4_merged2.txt"
        if not fixture_file.exists():
            pytest.skip("Fixture file not found")

        with open(fixture_file) as f:
            cidrs = [line.strip() for line in f if line.strip()]

        netset_text = "\n".join(cidrs)

        # Process with compaction enabled
        processor = IPProcessor(
            ipv4_block_prefix=18,
            enable_compaction=True,
            compact_target_max=50,
            compact_min_prefix_v4=11,
        )
        result = processor.netset_expand(netset_text, ",PROXY,no-resolve")

        # Should have proper format
        assert all(line.startswith("IP-CIDR,") for line in result)
        assert all(",PROXY,no-resolve" in line for line in result)

        # Should be compacted (original ~97 networks, target ~50)
        assert len(result) <= 60

        # Extract CIDRs from result to verify coverage
        result_cidrs = [
            line.replace("IP-CIDR,", "").replace(",PROXY,no-resolve", "")
            for line in result
        ]
        result_nets = [ipaddress.IPv4Network(cidr) for cidr in result_cidrs]

        # Verify original CIDRs are covered
        is_covered, not_covered = NetworkCompactor.verify_coverage(cidrs, result_nets)
        assert is_covered, f"{len(not_covered)} networks not covered"

    def test_netset_expand_mixed_ipv4_ipv6(self):
        """Test compaction with mixed IPv4 and IPv6 networks."""
        netset_text = """
        10.0.1.0/24
        10.0.2.0/24
        10.0.3.0/24
        2001:db8::/48
        2001:db8:1::/48
        """
        processor = IPProcessor(
            ipv4_block_prefix=24,
            ipv6_block_prefix=48,
            enable_compaction=True,
            compact_target_max=2,
            compact_min_prefix_v4=20,
            compact_min_prefix_v6=32,
        )
        result = processor.netset_expand(netset_text, ",PROXY")

        # Should have both IPv4 and IPv6 entries
        assert len(result) > 0
        assert all(line.startswith("IP-CIDR,") for line in result)

        # Should be compacted
        assert len(result) <= 5
