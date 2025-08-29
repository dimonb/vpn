"""Utility functions for IP address and CIDR block processing.

This module implements the logic from Cloudflare Worker v4 for processing
RULE-SET templates and expanding NETSET entries with IP aggregation.
"""

import ipaddress
import re
from typing import List, Tuple, Set, Dict, Any
from urllib.parse import urlparse
import asyncio
import aiohttp


# Regular expressions for IP validation and parsing
RE_IPV4_CIDR = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}\/(?:[0-9]|[12][0-9]|3[0-2])$")
RE_IPV6_CIDR = re.compile(r"^([0-9a-f:]+:+)+\/\d{1,3}$", re.IGNORECASE)
RULE_RE = re.compile(r"^\s*RULE-SET\s*,\s*([^,\s]+)\s*,\s*([^#]+?)\s*(?:#.*)?$", re.IGNORECASE)
NETSET_RE = re.compile(r"^#NETSET\s+(\S+)", re.IGNORECASE)


class IPProcessor:
    """IP address processor with aggregation capabilities."""
    
    def __init__(self, ipv4_block_prefix: int = 18, ipv6_block_prefix: int = 32):
        """Initialize processor with block prefix settings.
        
        Args:
            ipv4_block_prefix: Target prefix for IPv4 aggregation (default: 18)
            ipv6_block_prefix: Target prefix for IPv6 aggregation (default: 32)
        """
        self.ipv4_block_prefix = ipv4_block_prefix
        self.ipv6_block_prefix = ipv6_block_prefix
    
    def ipv4_cover_blocks(self, cidr: str) -> List[str]:
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
    
    def ipv6_cidr_to_blocks(self, cidr: str) -> List[str]:
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
                f"{floored_addr}/{self.ipv6_block_prefix}", 
                strict=False
            )
            
            return [f"{floored_network.network_address}/{self.ipv6_block_prefix}"]
            
        except ipaddress.AddressValueError as e:
            raise ValueError(f"Invalid IPv6 CIDR: {cidr}") from e
    
    def netset_expand(self, text: str, suffix: str) -> List[str]:
        """Expand raw .netset text into lines with IP aggregation.
        
        This implements the same logic as the Cloudflare Worker's netsetExpand function.
        It processes each line, handles IPv4/IPv6 CIDR blocks, and applies aggregation.
        
        Args:
            text: Raw netset text content
            suffix: Suffix to append to each IP-CIDR rule (e.g., ",PROXY,no-resolve")
            
        Returns:
            List of expanded and deduplicated rules
        """
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
                    blocks = self.ipv6_cidr_to_blocks(line)
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
                blocks4 = self.ipv4_cover_blocks(line)
                for block in blocks4:
                    out.append(f"IP-CIDR,{block}{suffix}")
        
        return self.dedupe_lines(out)
    
    def dedupe_lines(self, lines: List[str]) -> List[str]:
        """Stable de-duplication while preserving first occurrence order.
        
        This implements the same logic as the Cloudflare Worker's dedupeLines function.
        
        Args:
            lines: List of lines to deduplicate
            
        Returns:
            Deduplicated list preserving order
        """
        seen: Set[str] = set()
        out = []
        
        for line in lines:
            key = line.strip()
            if key and key not in seen:
                seen.add(key)
                out.append(line)
        
        return out


class TemplateProcessor:
    """Template processor for RULE-SET expansion."""
    
    def __init__(self, ip_processor: IPProcessor):
        """Initialize template processor.
        
        Args:
            ip_processor: IPProcessor instance for handling IP operations
        """
        self.ip_processor = ip_processor
    
    def parse_template(self, template_text: str) -> Dict[str, Any]:
        """Parse template text and extract RULE-SET entries.
        
        This implements the same logic as the Cloudflare Worker's parseTemplate function.
        
        Args:
            template_text: Raw template text content
            
        Returns:
            Dictionary with tasks, passthrough lines, and original line count
        """
        lines = template_text.split('\n')
        tasks = []
        passthrough = {}
        
        for index, raw_line in enumerate(lines):
            match = RULE_RE.match(raw_line)
            if not match:
                passthrough[index] = raw_line
                continue
            
            list_url = match.group(1).strip()
            suffix = f",{match.group(2).strip()}"  # keep commas e.g. ",PROXY,no-resolve"
            tasks.append({'index': index, 'url': list_url, 'suffix': suffix})
        
        return {
            'tasks': tasks,
            'passthrough': passthrough,
            'original_line_count': len(lines)
        }
    
    async def expand_netset(self, url: str, suffix: str, session: aiohttp.ClientSession) -> List[str]:
        """Expand NETSET from URL.
        
        This implements the same logic as the Cloudflare Worker's expandNetset function.
        
        Args:
            url: URL to fetch NETSET from
            suffix: Suffix to append to rules
            session: aiohttp session for HTTP requests
            
        Returns:
            List of expanded rules
        """
        try:
            resp = await session.get(url)
            if not resp.ok:
                return [f"# NETSET fetch failed: {url} ({resp.status})"]
            
            text = await resp.text()
            expanded = self.ip_processor.netset_expand(text, suffix)
            return expanded
            
        except Exception as e:
            return [f"# NETSET error: {url} - {str(e)}"]
    
    async def expand_rule_set(self, task: Dict[str, Any], session: aiohttp.ClientSession) -> List[str]:
        """Expand RULE-SET from URL.
        
        This implements the same logic as the Cloudflare Worker's expandRuleSet function.
        
        Args:
            task: Task dictionary with url and suffix
            session: aiohttp session for HTTP requests
            
        Returns:
            List of expanded rules
        """
        url = task['url']
        suffix = task['suffix']
        
        try:
            resp = await session.get(url)
            if not resp.ok:
                return [f"# RULE-SET fetch failed: {url} ({resp.status})"]
            
            text = await resp.text()
            lines = text.split('\n')
            
            # Extract NETSET URLs
            netset_urls = []
            for line in lines:
                line = line.strip()
                match = NETSET_RE.match(line)
                if match:
                    netset_urls.append(match.group(1))
            
            if netset_urls:
                # Expand NETSETs in parallel
                jobs = [self.expand_netset(ns_url, suffix, session) for ns_url in netset_urls]
                results = await asyncio.gather(*jobs)
                merged = self.ip_processor.dedupe_lines([item for sublist in results for item in sublist])
                return [f"# RULE-SET,{url}"] + merged
            
            # Process regular rules
            out = [f"# RULE-SET,{url}"]
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Remove comments
                hash_pos = line.find('#')
                if hash_pos != -1:
                    line = line[:hash_pos].strip()
                if not line:
                    continue
                
                # Normalize commas
                line = re.sub(r'\s+,', ',', line)
                line = re.sub(r',\s+', ',', line)
                
                # Handle proxy/direct/reject rules
                if re.search(r'(,PROXY|,DIRECT|,REJECT)\s*$', line, re.IGNORECASE):
                    line = re.sub(r',(PROXY|DIRECT|REJECT)\s*$', suffix, line, flags=re.IGNORECASE)
                else:
                    line = f"{line}{suffix}"
                
                out.append(line)
            
            return self.ip_processor.dedupe_lines(out)
            
        except Exception as e:
            return [f"# RULE-SET error: {url} - {str(e)}"]
    
    async def process_template(self, template_text: str) -> str:
        """Process template and expand all RULE-SET entries.
        
        This implements the same logic as the Cloudflare Worker's processTemplate function.
        
        Args:
            template_text: Raw template text content
            
        Returns:
            Processed template with expanded RULE-SET entries
        """
        parsed = self.parse_template(template_text)
        tasks = parsed['tasks']
        passthrough = parsed['passthrough']
        original_line_count = parsed['original_line_count']
        
        # Expand all RULE-SET entries in parallel
        async with aiohttp.ClientSession() as session:
            expansions = await asyncio.gather(*[
                self.expand_rule_set(task, session) for task in tasks
            ])
        
        # Merge results with passthrough lines
        output = []
        task_by_index = {task['index']: expansions[i] for i, task in enumerate(tasks)}
        
        for i in range(original_line_count):
            if i in task_by_index:
                output.extend(task_by_index[i])
            else:
                output.append(passthrough.get(i, ''))
        
        # Final deduplication
        final_output = self.ip_processor.dedupe_lines(output)
        return '\n'.join(final_output)


# Convenience functions for backward compatibility
def ipv4_cover_blocks(cidr: str, target_pfx: int = 18) -> List[str]:
    """Return list of covering IPv4 blocks with target prefix."""
    processor = IPProcessor(ipv4_block_prefix=target_pfx)
    return processor.ipv4_cover_blocks(cidr)


def ipv6_cidr_to_blocks(cidr: str, target_pfx: int = 32) -> List[str]:
    """Convert IPv6 CIDR to list of target prefix blocks."""
    processor = IPProcessor(ipv6_block_prefix=target_pfx)
    return processor.ipv6_cidr_to_blocks(cidr)


def dedupe_lines(lines: List[str]) -> List[str]:
    """Stable de-duplication while preserving first occurrence order."""
    processor = IPProcessor()
    return processor.dedupe_lines(lines)


def netset_expand(text: str, suffix: str, ipv4_block_prefix: int = 18, ipv6_block_prefix: int = 32) -> List[str]:
    """Expand raw .netset text into lines with IP aggregation."""
    processor = IPProcessor(ipv4_block_prefix=ipv4_block_prefix, ipv6_block_prefix=ipv6_block_prefix)
    return processor.netset_expand(text, suffix)
