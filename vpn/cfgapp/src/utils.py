"""Utility functions for IP address and CIDR block processing.

This module implements the logic from Cloudflare Worker v4 for processing
RULE-SET templates and expanding NETSET entries with IP aggregation.

It also includes an intelligent network compaction algorithm that reduces
large lists of CIDR blocks while maintaining full coverage.
"""

import ipaddress
import re
from typing import Optional

# Regular expressions for IP validation and parsing
RE_IPV4_CIDR = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}\/(?:[0-9]|[12][0-9]|3[0-2])$")
RE_IPV6_CIDR = re.compile(r"^([0-9a-f:]+:+)+\/\d{1,3}$", re.IGNORECASE)
RULE_RE = re.compile(
    r"^\s*RULE-SET\s*,\s*([^,\s]+)\s*,\s*([^#]+?)\s*(?:#.*)?$", re.IGNORECASE
)
NETSET_RE = re.compile(r"^#NETSET\s+(\S+)", re.IGNORECASE)


class IPProcessor:
    """IP address processor with aggregation capabilities."""

    def __init__(
        self,
        ipv4_block_prefix: int = 18,
        ipv6_block_prefix: int = 32,
        enable_compaction: bool = False,
        compact_target_max: int = 200,
        compact_min_prefix_v4: int = 11,
        compact_min_prefix_v6: int = 32,
    ):
        """Initialize processor with block prefix settings.

        Args:
            ipv4_block_prefix: Target prefix for IPv4 aggregation (default: 18)
            ipv6_block_prefix: Target prefix for IPv6 aggregation (default: 32)
            enable_compaction: Enable network compaction after processing (default: False)
            compact_target_max: Target number of networks after compaction (default: 200)
            compact_min_prefix_v4: Minimum IPv4 prefix for compaction (default: 11, max /11 = 2M IPs)
            compact_min_prefix_v6: Minimum IPv6 prefix for compaction (default: 32)
        """
        self.ipv4_block_prefix = ipv4_block_prefix
        self.ipv6_block_prefix = ipv6_block_prefix
        self.enable_compaction = enable_compaction
        self.compact_target_max = compact_target_max
        self.compact_min_prefix_v4 = compact_min_prefix_v4
        self.compact_min_prefix_v6 = compact_min_prefix_v6

    def ipv4_cover_blocks(self, cidr: str) -> list[str]:
        """Return list of covering IPv4 blocks with target prefix.

        This implements the same logic as the Cloudflare Worker's ipv4CoverBlocks function.
        It takes a CIDR block and returns a list of larger blocks that cover it.

        Args:
            cidr: IPv4 CIDR string (e.g., "192.168.1.0/24")

        Returns:
            List of covering CIDR blocks with target prefix

        Example:
            >>> processor = IPProcessor(ipv4_block_prefix=18)
            >>> processor.ipv4_cover_blocks("192.168.1.0/24")
            ['192.168.0.0/18']
        """
        try:
            network = ipaddress.IPv4Network(cidr, strict=False)

            # If the original network is already at the target prefix or larger
            if network.prefixlen == self.ipv4_block_prefix:
                return [f"{network.network_address}/{self.ipv4_block_prefix}"]
            elif network.prefixlen > self.ipv4_block_prefix:
                # Original network is smaller than target, need to aggregate
                pass

            # Get the start and end addresses of the original network
            start_addr = int(network.network_address)
            end_addr = int(network.broadcast_address)

            # Calculate block size for target prefix
            block_size = 2 ** (32 - self.ipv4_block_prefix)

            # Floor the start address to the target prefix
            # This is equivalent to floorToPrefixV4 in the Cloudflare Worker
            # Apply mask to get the network address for the target prefix
            mask = (0xFFFFFFFF << (32 - self.ipv4_block_prefix)) & 0xFFFFFFFF
            cursor = start_addr & mask

            blocks = []
            while cursor <= end_addr:
                # Convert cursor back to IP address
                ip_addr = ipaddress.IPv4Address(cursor)
                blocks.append(f"{ip_addr}/{self.ipv4_block_prefix}")

                # Move to next block
                cursor = (cursor + block_size) & 0xFFFFFFFF

            return blocks

        except ipaddress.AddressValueError as e:
            raise ValueError(f"Invalid IPv4 CIDR: {cidr}") from e

    def ipv6_cidr_to_blocks(self, cidr: str) -> list[str]:
        """Convert IPv6 CIDR to list of target prefix blocks.

        This implements the same logic as the Cloudflare Worker's ipv6CidrToBlocks function.
        It handles IPv6 aggregation by flooring addresses to the target prefix.

        Args:
            cidr: IPv6 CIDR string (e.g., "2001:db8::/32")

        Returns:
            List of covering CIDR blocks with target prefix

        Example:
            >>> processor = IPProcessor(ipv6_block_prefix=32)
            >>> processor.ipv6_cidr_to_blocks("2001:db8::/48")
            ['2001:db8::/32']
        """
        try:
            network = ipaddress.IPv6Network(cidr, strict=False)

            # If the original network is already at or larger than target prefix
            if network.prefixlen == self.ipv6_block_prefix:
                return [f"{network.network_address}/{self.ipv6_block_prefix}"]

            # Floor the starting address to the target prefix (same as Cloudflare Worker)
            # Convert to integer, apply mask, convert back
            addr_int = int(network.network_address)
            mask = (1 << (128 - self.ipv6_block_prefix)) - 1
            floored_addr_int = addr_int & ~mask

            # Create the floored network
            floored_addr = ipaddress.IPv6Address(floored_addr_int)
            floored_network = ipaddress.IPv6Network(
                f"{floored_addr}/{self.ipv6_block_prefix}", strict=False
            )

            return [f"{floored_network.network_address}/{self.ipv6_block_prefix}"]

        except ipaddress.AddressValueError as e:
            raise ValueError(f"Invalid IPv6 CIDR: {cidr}") from e

    def netset_expand(self, text: str, suffix: str) -> list[str]:
        """Expand raw .netset text into lines with IP aggregation.

        This implements the same logic as the Cloudflare Worker's netsetExpand function.
        It processes each line, handles IPv4/IPv6 CIDR blocks, and applies aggregation.

        If enable_compaction is True, applies NetworkCompactor to reduce the number
        of resulting CIDR blocks while maintaining full coverage.

        Args:
            text: Raw netset text content
            suffix: Suffix to append to each IP-CIDR rule (e.g., ",PROXY,no-resolve")

        Returns:
            List of expanded and deduplicated rules
        """
        out = []

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            # Remove "IP " prefix if present
            line = re.sub(r"^IP\s+", "", line, flags=re.IGNORECASE)

            # Handle IPv6 CIDR
            if RE_IPV6_CIDR.match(line):
                try:
                    blocks = self.ipv6_cidr_to_blocks(line)
                    for block in blocks:
                        if block.startswith("#"):
                            out.append(block)
                        else:
                            out.append(f"IP-CIDR,{block}{suffix}")
                except ValueError as e:
                    print(f"IPv6 parse error for {line}: {e}")
                    out.append(f"IP-CIDR,{line}{suffix}")
                continue

            # Handle IPv4 CIDR
            if RE_IPV4_CIDR.match(line):
                blocks4 = self.ipv4_cover_blocks(line)
                for block in blocks4:
                    out.append(f"IP-CIDR,{block}{suffix}")

        # Deduplicate first
        out = self.dedupe_lines(out)

        # Apply network compaction if enabled
        if self.enable_compaction:
            out = self._apply_compaction(out, suffix)

        return out

    def _apply_compaction(self, lines: list[str], suffix: str) -> list[str]:
        """Apply network compaction to IP-CIDR lines.

        Extracts CIDR blocks, compacts them using NetworkCompactor,
        and reconstructs the IP-CIDR lines.

        Args:
            lines: List of IP-CIDR lines
            suffix: Suffix that was used in original lines

        Returns:
            List of compacted IP-CIDR lines
        """
        # Separate IPv4 and IPv6 CIDRs from other lines
        ipv4_cidrs = []
        ipv6_cidrs = []
        other_lines = []

        for line in lines:
            if line.startswith("IP-CIDR,"):
                # Extract CIDR without prefix and suffix
                cidr = line[8:]  # Remove "IP-CIDR,"
                if suffix and cidr.endswith(suffix):
                    cidr = cidr[: -len(suffix)]

                # Detect IP version
                if RE_IPV4_CIDR.match(cidr):
                    ipv4_cidrs.append(cidr)
                elif RE_IPV6_CIDR.match(cidr):
                    ipv6_cidrs.append(cidr)
                else:
                    other_lines.append(line)
            else:
                other_lines.append(line)

        # Compact IPv4 networks
        if ipv4_cidrs:
            compacted_v4 = NetworkCompactor.compact_networks(
                ipv4_cidrs,
                target_max=self.compact_target_max,
                min_prefix=self.compact_min_prefix_v4,
                version=4,
            )
            ipv4_lines = [f"IP-CIDR,{net}{suffix}" for net in compacted_v4]
        else:
            ipv4_lines = []

        # Compact IPv6 networks
        if ipv6_cidrs:
            compacted_v6 = NetworkCompactor.compact_networks(
                ipv6_cidrs,
                target_max=self.compact_target_max,
                min_prefix=self.compact_min_prefix_v6,
                version=6,
            )
            ipv6_lines = [f"IP-CIDR,{net}{suffix}" for net in compacted_v6]
        else:
            ipv6_lines = []

        # Combine all lines: other lines first, then IPv4, then IPv6
        return other_lines + ipv4_lines + ipv6_lines

    def dedupe_lines(self, lines: list[str]) -> list[str]:
        """Stable de-duplication while preserving first occurrence order.

        This implements the same logic as the Cloudflare Worker's dedupeLines function.

        Args:
            lines: List of lines to deduplicate

        Returns:
            Deduplicated list preserving order
        """
        seen: set[str] = set()
        out = []

        for line in lines:
            key = line.strip()
            if key and key not in seen:
                seen.add(key)
                out.append(line)

        return out


class NetworkCompactor:
    """Intelligent network compaction with full coverage guarantee.

    This class implements an adaptive algorithm that reduces large lists of
    IPv4/IPv6 CIDR blocks while guaranteeing 100% coverage of original networks.
    """

    @staticmethod
    def find_minimal_supernet(
        nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
        min_prefix: int = 8,
    ) -> Optional[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Find the minimal supernet that covers all networks in the list.

        Args:
            nets: List of IPv4Network or IPv6Network objects
            min_prefix: Minimum prefix length (maximum network size)

        Returns:
            Minimal supernet or None if cannot be found
        """
        if not nets:
            return None

        # All networks must be of the same type
        is_ipv4 = isinstance(nets[0], ipaddress.IPv4Network)
        max_bits = 32 if is_ipv4 else 128

        # Find address range
        min_addr = min(int(net.network_address) for net in nets)
        max_addr = max(int(net.broadcast_address) for net in nets)

        # Find minimal prefix that covers this range
        for prefix_len in range(min_prefix, max_bits + 1):
            size = 1 << (max_bits - prefix_len)
            base = min_addr & ~(size - 1)

            # Check if this network covers all addresses
            if base + size - 1 >= max_addr:
                # Create candidate network
                if is_ipv4:
                    candidate = ipaddress.IPv4Network((base, prefix_len))
                else:
                    candidate = ipaddress.IPv6Network((base, prefix_len))

                # Verify all networks are subnets
                if all(net.subnet_of(candidate) for net in nets):
                    return candidate

        return None

    @staticmethod
    def compact_networks(
        cidrs: list[str],
        target_max: int = 200,
        min_prefix: int = 11,
        version: int = 4,
    ) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Compact a list of CIDR networks to approximately target_max entries.

        This algorithm guarantees 100% coverage of all original networks while
        minimizing the number of resulting networks and limiting the increase
        in IP address coverage.

        Args:
            cidrs: List of CIDR strings (e.g., ["192.168.0.0/24", "10.0.0.0/8"])
            target_max: Target maximum number of networks (approximate)
            min_prefix: Minimum prefix length (maximum network size)
                       For IPv4: 8=/8 (16M IPs), 11=/11 (2M IPs), 12=/12 (1M IPs)
            version: IP version (4 or 6)

        Returns:
            List of compacted network objects

        Example:
            >>> compactor = NetworkCompactor()
            >>> cidrs = ["192.168.0.0/24", "192.168.1.0/24"]
            >>> result = compactor.compact_networks(cidrs, target_max=1, min_prefix=16)
            >>> [str(net) for net in result]
            ['192.168.0.0/23']
        """
        if version == 4:
            nets = [ipaddress.IPv4Network(c) for c in cidrs]
        else:
            nets = [ipaddress.IPv6Network(c) for c in cidrs]

        original_coverage = sum(net.num_addresses for net in nets)

        # Basic collapse to remove overlaps
        nets = list(ipaddress.collapse_addresses(nets))

        if len(nets) <= target_max:
            return nets

        # Adaptive merging with increasing cost thresholds
        # Cost = additional IP addresses added by merging
        thresholds = [1048576, 2097152, 4194304, 8388608, 16777216]

        for threshold in thresholds:
            changed = True

            while changed and len(nets) > target_max:
                changed = False

                # Sort by network address for neighbor detection
                nets = sorted(nets, key=lambda n: int(n.network_address))

                i = 0
                while i < len(nets) - 1 and len(nets) > target_max:
                    net1, net2 = nets[i], nets[i + 1]

                    # Try to find minimal supernet for this pair
                    supernet = NetworkCompactor.find_minimal_supernet(
                        [net1, net2], min_prefix
                    )

                    if supernet:
                        # Calculate cost (additional IPs)
                        cost = (
                            supernet.num_addresses
                            - net1.num_addresses
                            - net2.num_addresses
                        )

                        if cost <= threshold:
                            # Merge the pair
                            nets = nets[:i] + [supernet] + nets[i + 2 :]
                            nets = list(ipaddress.collapse_addresses(nets))
                            changed = True
                            # Don't increment i to check new network with next
                        else:
                            i += 1
                    else:
                        i += 1

            # Check if we've reached target
            if len(nets) <= target_max:
                break

        return nets

    @staticmethod
    def verify_coverage(
        original_cidrs: list[str],
        compacted_nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
    ) -> tuple[bool, list[str]]:
        """Verify that all original networks are covered by compacted networks.

        Args:
            original_cidrs: Original list of CIDR strings
            compacted_nets: Compacted list of network objects

        Returns:
            Tuple of (is_fully_covered, list_of_not_covered_cidrs)
        """
        # Detect IP version from first CIDR
        if not original_cidrs:
            return (True, [])

        # Try to parse as IPv4 first
        try:
            ipaddress.IPv4Network(original_cidrs[0])
            original_nets = [ipaddress.IPv4Network(c) for c in original_cidrs]
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            original_nets = [ipaddress.IPv6Network(c) for c in original_cidrs]

        not_covered = []
        for orig_net in original_nets:
            is_covered = any(
                orig_net.subnet_of(comp_net) or orig_net == comp_net
                for comp_net in compacted_nets
            )
            if not is_covered:
                not_covered.append(str(orig_net))

        return (len(not_covered) == 0, not_covered)


# Convenience functions for backward compatibility
def ipv4_cover_blocks(cidr: str, target_pfx: int = 18) -> list[str]:
    """Return list of covering IPv4 blocks with target prefix."""
    processor = IPProcessor(ipv4_block_prefix=target_pfx)
    return processor.ipv4_cover_blocks(cidr)


def ipv6_cidr_to_blocks(cidr: str, target_pfx: int = 32) -> list[str]:
    """Convert IPv6 CIDR to list of target prefix blocks."""
    processor = IPProcessor(ipv6_block_prefix=target_pfx)
    return processor.ipv6_cidr_to_blocks(cidr)


def dedupe_lines(lines: list[str]) -> list[str]:
    """Stable de-duplication while preserving first occurrence order."""
    processor = IPProcessor()
    return processor.dedupe_lines(lines)


def netset_expand(
    text: str,
    suffix: str,
    ipv4_block_prefix: int = 18,
    ipv6_block_prefix: int = 32,
    enable_compaction: bool = False,
    compact_target_max: int = 200,
    compact_min_prefix_v4: int = 11,
    compact_min_prefix_v6: int = 32,
) -> list[str]:
    """Expand raw .netset text into lines with IP aggregation.

    Args:
        text: Raw netset text content
        suffix: Suffix to append to each IP-CIDR rule
        ipv4_block_prefix: Target prefix for IPv4 aggregation (default: 18)
        ipv6_block_prefix: Target prefix for IPv6 aggregation (default: 32)
        enable_compaction: Enable network compaction after processing (default: False)
        compact_target_max: Target number of networks after compaction (default: 200)
        compact_min_prefix_v4: Minimum IPv4 prefix for compaction (default: 11)
        compact_min_prefix_v6: Minimum IPv6 prefix for compaction (default: 32)

    Returns:
        List of expanded and optionally compacted rules
    """
    processor = IPProcessor(
        ipv4_block_prefix=ipv4_block_prefix,
        ipv6_block_prefix=ipv6_block_prefix,
        enable_compaction=enable_compaction,
        compact_target_max=compact_target_max,
        compact_min_prefix_v4=compact_min_prefix_v4,
        compact_min_prefix_v6=compact_min_prefix_v6,
    )
    return processor.netset_expand(text, suffix)


def compact_ipv4_networks(
    cidrs: list[str], target_max: int = 200, min_prefix: int = 11
) -> list[str]:
    """Compact IPv4 CIDR list with guaranteed full coverage.

    Args:
        cidrs: List of IPv4 CIDR strings
        target_max: Target maximum number of networks
        min_prefix: Minimum prefix (8-32, smaller = larger networks)

    Returns:
        List of compacted CIDR strings

    Example:
        >>> cidrs = ["192.168.0.0/24", "192.168.1.0/24", "192.168.2.0/24"]
        >>> result = compact_ipv4_networks(cidrs, target_max=2, min_prefix=20)
        >>> result
        ['192.168.0.0/22']
    """
    nets = NetworkCompactor.compact_networks(
        cidrs, target_max=target_max, min_prefix=min_prefix, version=4
    )
    return [str(net) for net in nets]


def compact_ipv6_networks(
    cidrs: list[str], target_max: int = 200, min_prefix: int = 32
) -> list[str]:
    """Compact IPv6 CIDR list with guaranteed full coverage.

    Args:
        cidrs: List of IPv6 CIDR strings
        target_max: Target maximum number of networks
        min_prefix: Minimum prefix (8-128, smaller = larger networks)

    Returns:
        List of compacted CIDR strings
    """
    nets = NetworkCompactor.compact_networks(
        cidrs, target_max=target_max, min_prefix=min_prefix, version=6
    )
    return [str(net) for net in nets]
