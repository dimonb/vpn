"""Utility functions for IP address and CIDR block processing."""

import ipaddress
import re
from typing import List, Tuple, Set
from .config import settings


# Regular expressions for IP validation
RE_IPV4_CIDR = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}\/(?:[0-9]|[12][0-9]|3[0-2])$")
RE_IPV6_CIDR = re.compile(r"^([0-9a-f:]+:+)+\/\d{1,3}$", re.IGNORECASE)


def ip_to_int(ip: str) -> int:
    """Convert IPv4 address string to integer."""
    return int(ipaddress.IPv4Address(ip))


def int_to_ip(n: int) -> str:
    """Convert integer to IPv4 address string."""
    return str(ipaddress.IPv4Address(n))


def cidr_range_v4(cidr: str) -> Tuple[int, int]:
    """Get start and end addresses for IPv4 CIDR block."""
    network = ipaddress.IPv4Network(cidr, strict=False)
    return int(network.network_address), int(network.broadcast_address)


def floor_to_prefix_v4(addr: int, target_pfx: int) -> int:
    """Floor IPv4 address to target prefix."""
    mask = (0xFFFFFFFF << (32 - target_pfx)) & 0xFFFFFFFF
    return addr & mask


def block_size_v4(target_pfx: int) -> int:
    """Calculate block size for IPv4 prefix."""
    return 2 ** (32 - target_pfx)


def ipv4_cover_blocks(cidr: str, target_pfx: int) -> List[str]:
    """Return list of covering IPv4 blocks with target prefix."""
    start, end = cidr_range_v4(cidr)
    size = block_size_v4(target_pfx)
    cursor = floor_to_prefix_v4(start, target_pfx)
    blocks = []
    
    while cursor <= end:
        blocks.append(f"{int_to_ip(cursor)}/{target_pfx}")
        cursor = (cursor + size) & 0xFFFFFFFF
    
    return blocks


def parse_ipv6_to_bigint(ipv6: str) -> int:
    """Parse IPv6 address to BigInt representation."""
    try:
        return int(ipaddress.IPv6Address(ipv6))
    except ipaddress.AddressValueError as e:
        raise ValueError(f"Invalid IPv6 address: {ipv6}") from e


def ipv6_cidr_to_blocks(cidr: str, target_pfx: int = None) -> List[str]:
    """Convert IPv6 CIDR to list of target prefix blocks."""
    if target_pfx is None:
        target_pfx = settings.ipv6_block_prefix
    
    try:
        network = ipaddress.IPv6Network(cidr, strict=False)
        target_network = ipaddress.IPv6Network(f"{network.network_address}/{target_pfx}", strict=False)
        
        # Calculate how many /target_pfx blocks fit in the original CIDR
        original_size = network.num_addresses
        target_size = target_network.num_addresses
        
        if original_size <= target_size:
            # Original CIDR is smaller than or equal to target prefix
            return [f"{network.network_address}/{target_pfx}"]
        
        # Calculate the number of target blocks needed
        num_blocks = original_size // target_size
        if num_blocks > 262144:  # Cap at reasonable number
            return [
                f"{network.network_address}/{target_pfx}",
                f"# WARNING: truncated {num_blocks - 1} blocks for {cidr}"
            ]
        
        blocks = []
        current_network = target_network
        for _ in range(num_blocks):
            blocks.append(f"{current_network.network_address}/{target_pfx}")
            # Move to next block
            next_addr = current_network.network_address + target_size
            current_network = ipaddress.IPv6Network(f"{next_addr}/{target_pfx}", strict=False)
        
        return blocks
    
    except ipaddress.AddressValueError as e:
        raise ValueError(f"Invalid IPv6 CIDR: {cidr}") from e


def dedupe_lines(lines: List[str]) -> List[str]:
    """Stable de-duplication while preserving first occurrence order."""
    seen: Set[str] = set()
    out = []
    
    for line in lines:
        key = line.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(line)
    
    return out


def netset_expand(text: str, suffix: str) -> List[str]:
    """Expand raw .netset text into lines, IPv4 -> /19, IPv6 -> /32."""
    out = []
    
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        
        # Remove "IP " prefix if present
        line = re.sub(r'^IP\s+', '', line, flags=re.IGNORECASE)
        
        # Handle IPv6 CIDR
        if RE_IPV6_CIDR.match(line):
            try:
                blocks = ipv6_cidr_to_blocks(line, settings.ipv6_block_prefix)
                for block in blocks:
                    if block.startswith('#'):
                        out.append(block)
                    else:
                        out.append(f"IP-CIDR,{block}{suffix}")
            except ValueError as e:
                print(f"IPv6 parse error for {line}: {e}")
                out.append(f"IP-CIDR,{line}{suffix}")
            continue
        
        # Handle IPv4 CIDR
        if RE_IPV4_CIDR.match(line):
            blocks4 = ipv4_cover_blocks(line, settings.ipv4_block_prefix)
            for block in blocks4:
                out.append(f"IP-CIDR,{block}{suffix}")
    
    return out
