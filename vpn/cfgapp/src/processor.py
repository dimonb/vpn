"""Core processing logic for RULE-SET and NETSET expansion."""

import asyncio
import re
import traceback
from urllib.parse import urlparse

import httpx

from .config import settings
from .utils import dedupe_lines, netset_expand

# Regular expressions for parsing
RULE_RE = re.compile(
    r"^\s*RULE-SET\s*,\s*([^,\s]+)\s*,\s*([^#]+?)\s*(?:#.*)?$", re.IGNORECASE
)
NETSET_RE = re.compile(r"^#NETSET\s+(\S+)", re.IGNORECASE)


class TemplateProcessor:
    """Process template files and expand RULE-SET entries."""

    def __init__(self, http_client: httpx.AsyncClient):
        """Initialize processor with HTTP client."""
        self.http_client = http_client

    async def smart_fetch(
        self, url_str: str, incoming_host: str, request_headers: dict
    ) -> str:
        """Fetch URL with smart proxying for same/ALT hosts."""
        parsed_url = urlparse(url_str)

        if parsed_url.netloc == incoming_host and settings.api_host:
            # Proxy via API_HOST for same host
            path = parsed_url.path + (
                "?" + parsed_url.query if parsed_url.query else ""
            )
            proxy_url = f"https://{settings.api_host}{path}"
            print(f"Same host detected; proxy via origin for: {path}")

            headers = dict(request_headers)
            headers.pop("cookie", None)  # Remove cookies

            response = await self.http_client.get(proxy_url, headers=headers)
            response.raise_for_status()
            return response.text
        else:
            # Direct fetch for external URLs (including ALT_HOST)
            print(f"Direct fetch for: {url_str}")
            response = await self.http_client.get(url_str)
            response.raise_for_status()
            return response.text

    async def expand_netset(self, url_str: str, suffix: str) -> list[str]:
        """Fetch and expand NETSET file."""
        print(f"Fetching NETSET: {url_str}")
        try:
            response = await self.http_client.get(url_str)
            if not response.is_success:
                print(f"NETSET fetch failed: {response.status_code}")
                return [f"# NETSET fetch failed: {url_str} ({response.status_code})"]

            text = response.text
            expanded = netset_expand(
                text,
                suffix,
                ipv4_block_prefix=settings.ipv4_block_prefix,
                ipv6_block_prefix=settings.ipv6_block_prefix,
            )
            print(
                f"NETSET expanded {len(expanded)} entries (IPv4→/{settings.ipv4_block_prefix}, IPv6→/{settings.ipv6_block_prefix})"
            )
            return expanded

        except Exception as e:
            print(f"NETSET error {url_str}: {str(e)}")
            return [f"# NETSET error: {url_str}"]

    def parse_template(
        self, template_text: str
    ) -> tuple[list[dict], list[str | None], int]:
        """Parse template text and extract RULE-SET tasks."""
        lines = template_text.split("\n")
        tasks = []
        passthrough = [None] * len(lines)

        for index, raw_line in enumerate(lines):
            match = RULE_RE.match(raw_line)
            if not match:
                passthrough[index] = raw_line
                continue

            list_url = match.group(1).strip()
            suffix = (
                f",{match.group(2).strip()}"  # Keep commas e.g. ",PROXY,no-resolve"
            )
            tasks.append({"index": index, "url": list_url, "suffix": suffix})

        return tasks, passthrough, len(lines)

    async def expand_rule_set(
        self, task: dict, incoming_host: str, request_headers: dict
    ) -> list[str]:
        """Expand a single RULE-SET entry."""
        url = task["url"]
        suffix = task["suffix"]

        print(f'Expanding RULE-SET: {url} with suffix "{suffix}"')

        try:
            text = await self.smart_fetch(url, incoming_host, request_headers)
            lines = text.split("\n")

            # Extract NETSET URLs
            netset_urls = []
            for line in lines:
                line = line.strip()
                match = NETSET_RE.match(line)
                if match:
                    netset_urls.append(match.group(1))

            # Process regular rules first
            output = [f"# RULE-SET,{url}"]
            for line in lines:
                trimmed = line.strip()
                if not trimmed or trimmed.startswith("#"):
                    continue

                # Remove comments
                hash_pos = trimmed.find("#")
                if hash_pos != -1:
                    trimmed = trimmed[:hash_pos].strip()
                if not trimmed:
                    continue

                # Normalize commas
                trimmed = re.sub(r"\s+,", ",", trimmed)
                trimmed = re.sub(r",\s+", ",", trimmed)

                # Handle proxy/direct/reject suffixes
                if re.search(r",(PROXY|DIRECT|REJECT)\s*$", trimmed, re.IGNORECASE):
                    trimmed = re.sub(
                        r",(PROXY|DIRECT|REJECT)\s*$",
                        suffix,
                        trimmed,
                        flags=re.IGNORECASE,
                    )
                else:
                    trimmed = f"{trimmed}{suffix}"

                output.append(trimmed)

            # Process NETSET entries if any
            if netset_urls:
                print(
                    f"Found {len(netset_urls)} NETSET entr{'ies' if len(netset_urls) > 1 else 'y'} in {url}"
                )
                jobs = [self.expand_netset(ns_url, suffix) for ns_url in netset_urls]
                results = await asyncio.gather(*jobs)
                netset_results = [item for sublist in results for item in sublist]
                output.extend(netset_results)
                return dedupe_lines(output)

            return dedupe_lines(output)

        except Exception as e:
            print(f"List fetch failed: {url} -> {str(e)}")
            traceback.print_exc()
            return [f"# RULE-SET fetch failed: {url}"]

    async def process_template(
        self, tpl_text: str, incoming_host: str = "", request_headers: dict = None
    ) -> str:
        """Process template: run all RULE-SET expands in parallel and merge."""
        if request_headers is None:
            request_headers = {}
        tasks, passthrough, original_line_count = self.parse_template(tpl_text)
        print(
            f"Template parsed: {original_line_count} lines, {len(tasks)} RULE-SET task(s)"
        )

        # Expand all RULE-SET entries in parallel
        expansions = await asyncio.gather(
            *[
                self.expand_rule_set(task, incoming_host, request_headers)
                for task in tasks
            ]
        )

        # Merge results with passthrough lines
        output = []
        task_by_index = {task["index"]: expansions[i] for i, task in enumerate(tasks)}

        for i in range(original_line_count):
            if i in task_by_index:
                output.extend(task_by_index[i])
            else:
                output.append(passthrough[i] or "")

        final_output = dedupe_lines(output)
        print(f"Template expansion complete. Total lines: {len(final_output)}")
        return "\n".join(final_output)
