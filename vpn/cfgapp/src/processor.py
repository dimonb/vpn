"""Core processing logic for RULE-SET and NETSET expansion."""

import asyncio
import logging
import re
import time
from urllib.parse import urlparse

import httpx

from .config import settings
from .listcache import ListCache
from .utils import dedupe_lines, netset_expand

logger = logging.getLogger(__name__)

# Regular expressions for parsing
RULE_RE = re.compile(
    r"^\s*RULE-SET\s*,\s*([^,\s]+)\s*,\s*([^#]+?)\s*(?:#.*)?$", re.IGNORECASE
)
NETSET_RE = re.compile(r"^#NETSET\s+(\S+)", re.IGNORECASE)

# RULE-SET / NETSET list fetches are large, cacheable bodies and are *not*
# latency-sensitive (unlike the origin fetch in main.py, which keeps its own
# short ORIGIN_TIMEOUT). On a relay they also travel through the sing-box
# tunnel, and on a CPU-starved VPS httpx's 5 s default expired mid-fetch — the
# list was then silently dropped from the rendered config, so the same URL
# returned a truncated body on some requests. Be patient, and retry.
LIST_TIMEOUT = 15.0
LIST_ATTEMPTS = 3

# Once a list has failed, do not let every subsequent request re-discover that
# for itself: a full retry cycle costs LIST_ATTEMPTS * LIST_TIMEOUT, and with the
# cache serving a stale copy anyway the only thing those seconds buy is a slow
# endpoint during someone else's outage. Recheck at most this often.
LIST_FAILURE_BACKOFF = 60.0

# Serving a stale copy is a fallback, not a steady state. Past this age it means
# the URL has been broken for days (repo renamed, file moved) and nobody noticed,
# because the endpoint kept answering 200 — so say so at a level that pages.
LIST_STALE_ALERT_SECONDS = 3 * 24 * 60 * 60

# Concurrent requests all expand the same handful of lists, so a TTL expiry would
# otherwise send N identical fetches upstream at once. One request refreshes;
# the rest wait for it and read what it wrote. Keyed by cache key, per process.
_refresh_locks: dict[str, asyncio.Lock] = {}
_failed_until: dict[str, float] = {}
_failed_reason: dict[str, object] = {}


def _refresh_lock(key: str) -> asyncio.Lock:
    """Lock guarding refreshes of one cache key."""
    lock = _refresh_locks.get(key)
    if lock is None:
        lock = _refresh_locks[key] = asyncio.Lock()
    return lock


def _in_backoff(key: str) -> bool:
    """True while a recent failure means we should not re-probe this list."""
    return time.monotonic() < _failed_until.get(key, 0.0)


def _record_failure(key: str, reason: object) -> None:
    """Remember why a list failed, so waiters can fail the same way, fast."""
    _failed_until[key] = time.monotonic() + LIST_FAILURE_BACKOFF
    _failed_reason[key] = reason


def _clear_failure(key: str) -> None:
    _failed_until.pop(key, None)
    _failed_reason.pop(key, None)


class ListFetchError(Exception):
    """A RULE-SET/NETSET list could not be fetched.

    Must propagate all the way to the request handler: a config rendered
    without one of its lists looks perfectly valid to a client, which then
    replaces a working subscription with one missing whole CIDR blocks. An
    error instead lets the client keep its last good config.
    """

    def __init__(self, url: str, reason: object):
        super().__init__(f"{url}: {reason!r}")
        self.url = url
        self.reason = reason

    @property
    def is_timeout(self) -> bool:
        """True when the list was lost to a timeout (→ 504 rather than 502)."""
        return isinstance(self.reason, httpx.TimeoutException)


class TemplateProcessor:
    """Process template files and expand RULE-SET entries."""

    def __init__(
        self, http_client: httpx.AsyncClient, list_cache: ListCache | None = None
    ):
        """Initialize processor with HTTP client and its list cache."""
        self.http_client = http_client
        self.list_cache = list_cache or ListCache(
            settings.list_cache_dir,
            settings.list_cache_fresh_seconds,
            settings.list_cache_max_age_seconds,
        )
        self.own_hosts = {
            host.strip().lower()
            for host in (
                settings.list_cache_own_hosts.split(",")
                + [settings.config_host, settings.api_host]
            )
            if host.strip()
        }

    async def _fetch_list(self, url: str, **kwargs) -> httpx.Response:
        """GET a list URL, retrying transient transport/timeout failures.

        Each attempt is a fresh request, so a retry also re-resolves and can
        land on a different address.
        """
        last_error: Exception | None = None
        for attempt in range(1, LIST_ATTEMPTS + 1):
            try:
                return await self.http_client.get(url, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = e
                logger.warning(
                    f"List fetch attempt {attempt}/{LIST_ATTEMPTS} failed for {url}: {e!r}"
                )
        raise ListFetchError(url, last_error) from last_error

    @staticmethod
    def _raise_for_list_status(url: str, response: httpx.Response) -> None:
        """Turn anything that is not a complete list body into a hard failure.

        Not just non-2xx: a `204 No Content`, a `206 Partial Content` from a
        misbehaving proxy, or a zero-length `200` all pass ``raise_for_status``,
        and caching one of those would pin the truncation for a day and keep it
        as the fallback for a month — the exact failure this module exists to
        prevent, made sticky.
        """
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ListFetchError(url, e) from e
        if response.status_code != 200:
            raise ListFetchError(url, f"unexpected HTTP {response.status_code}")
        if not response.text.strip():
            raise ListFetchError(url, "empty body")

    def _fresh_seconds_for(self, url: str) -> float:
        """How long a copy may be served without asking upstream at all."""
        host = urlparse(url).netloc.rsplit("@", 1)[-1].rsplit(":", 1)[0].lower()
        if host in self.own_hosts:
            return settings.list_cache_own_fresh_seconds
        return self.list_cache.fresh_seconds

    def _serve_after_failure(self, url: str, key: str) -> str:
        """Answer from disk while a recent failure is still being backed off.

        Never falls through to a fetch: the whole point is that the request
        after a 45 s failure must not spend another 45 s proving it again.
        """
        cached = self.list_cache.read_stale(key)
        if cached is None:
            raise ListFetchError(url, _failed_reason.get(key, "upstream unavailable"))
        self._log_stale(key, cached.age, _failed_reason.get(key))
        return cached.text

    @staticmethod
    def _log_stale(key: str, age: float, reason: object) -> None:
        """A stale copy is a fallback; days of it is an outage nobody saw."""
        message = (
            f"List fetch failed ({reason!r}), serving cached copy "
            f"{age / 3600:.1f}h old: {key}"
        )
        if age > LIST_STALE_ALERT_SECONDS:
            logger.error(f"{message} — this list has been broken for days")
        else:
            logger.warning(message)

    async def fetch_list_text(
        self, url: str, cache_key: str | None = None, **kwargs
    ) -> str:
        """Return a list body, from the cache when it is young enough.

        Cache-first, network-second, cache-again-on-failure — see listcache.py
        for why. ``cache_key`` overrides the key when the URL actually fetched
        differs from the one the template names.
        """
        key = cache_key or url
        fresh_seconds = self._fresh_seconds_for(url)

        cached = self.list_cache.read(key, fresh_seconds)
        if cached is not None:
            logger.debug(f"List cache hit ({cached.age / 3600:.1f}h old): {key}")
            return cached.text

        if _in_backoff(key):
            return self._serve_after_failure(url, key)

        async with _refresh_lock(key):
            # Whoever held the lock may have just refreshed it for us...
            cached = self.list_cache.read(key, fresh_seconds)
            if cached is not None:
                return cached.text
            # ...or may have just failed. Re-check *inside* the lock: everyone
            # who queued up before the leader recorded its failure would
            # otherwise run their own full retry cycle, one after another, and
            # turn a slow upstream into an unbounded queue of 45 s requests.
            if _in_backoff(key):
                return self._serve_after_failure(url, key)

            try:
                response = await self._fetch_list(url, **kwargs)
                self._raise_for_list_status(url, response)
            except ListFetchError as e:
                _record_failure(key, e.reason)
                cached = self.list_cache.read_stale(key)
                if cached is None:
                    raise
                self._log_stale(key, cached.age, e.reason)
                return cached.text

            _clear_failure(key)
            self.list_cache.write(key, response.text)
            return response.text

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

            # Deliberately uncached: this is our own origin, the response varies
            # with the caller's headers, and a config edit must not take a day
            # to show up.
            response = await self._fetch_list(proxy_url, headers=headers)
            self._raise_for_list_status(url_str, response)
            return response.text
        else:
            # Direct fetch for external URLs (including ALT_HOST)
            print(f"Direct fetch for: {url_str}")
            return await self.fetch_list_text(url_str)

    async def expand_netset(self, url_str: str, suffix: str) -> list[str]:
        """Fetch and expand NETSET file.

        Raises ListFetchError instead of returning a placeholder comment: the
        caller must fail the request rather than serve the list's ranges away.
        """
        print(f"Fetching NETSET: {url_str}")
        text = await self.fetch_list_text(url_str)
        expanded = netset_expand(
            text,
            suffix,
            ipv4_block_prefix=settings.ipv4_block_prefix,
            ipv6_block_prefix=settings.ipv6_block_prefix,
            enable_compaction=settings.enable_compaction,
            compact_target_max=settings.compact_target_max,
            compact_min_prefix_v4=settings.compact_min_prefix_v4,
            compact_min_prefix_v6=settings.compact_min_prefix_v6,
        )
        compaction_info = (
            f" [compacted to ~{settings.compact_target_max}]"
            if settings.enable_compaction
            else ""
        )
        print(
            f"NETSET expanded {len(expanded)} entries (IPv4→/{settings.ipv4_block_prefix}, IPv6→/{settings.ipv6_block_prefix}){compaction_info}"
        )
        return expanded

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
        """Expand a single RULE-SET entry.

        Raises ListFetchError if the rule list — or any NETSET it references —
        cannot be fetched; the request must fail rather than render a config
        with those rules missing.
        """
        url = task["url"]
        suffix = task["suffix"]

        print(f'Expanding RULE-SET: {url} with suffix "{suffix}"')

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
