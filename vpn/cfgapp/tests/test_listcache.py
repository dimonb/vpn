"""Tests for the on-disk list cache and the cache-aware fetch path."""

import asyncio
import os
import time
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.listcache import ListCache
from src.processor import LIST_ATTEMPTS, ListFetchError, TemplateProcessor

DAY = 24 * 60 * 60
MONTH = 30 * DAY
URL = "https://raw.githubusercontent.com/example/repo/main/list.txt"


def age_file(cache: ListCache, key: str, seconds: float) -> None:
    """Backdate a cache entry, the way the passage of time would."""
    path = cache.path_for(key)
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


class TestListCache:
    """The store itself."""

    @pytest.fixture
    def cache(self, tmp_path) -> ListCache:
        return ListCache(tmp_path / "lists", fresh_seconds=DAY, max_age_seconds=MONTH)

    def test_roundtrip(self, cache: ListCache) -> None:
        cache.write(URL, "1.2.3.0/24")

        cached = cache.read_fresh(URL)
        assert cached is not None
        assert cached.text == "1.2.3.0/24"
        assert cached.age < 5

    def test_miss_on_empty_cache(self, cache: ListCache) -> None:
        assert cache.read_fresh(URL) is None
        assert cache.read_stale(URL) is None

    def test_day_old_copy_is_stale_but_usable(self, cache: ListCache) -> None:
        """Older than a day: refetch, but still good enough as a fallback."""
        cache.write(URL, "body")
        age_file(cache, URL, DAY + 60)

        assert cache.read_fresh(URL) is None
        cached = cache.read_stale(URL)
        assert cached is not None
        assert cached.text == "body"
        assert cached.age > DAY

    def test_month_old_copy_is_gone(self, cache: ListCache) -> None:
        cache.write(URL, "body")
        age_file(cache, URL, MONTH + 60)

        assert cache.read_fresh(URL) is None
        assert cache.read_stale(URL) is None

    def test_prune_removes_expired_entries(self, cache: ListCache) -> None:
        cache.write(URL, "body")
        other = "https://example.com/other.txt"
        cache.write(other, "other body")
        age_file(cache, other, MONTH + 60)

        cache.prune()

        assert cache.path_for(URL).exists()
        assert not cache.path_for(other).exists()

    def test_write_leaves_no_temp_files(self, cache: ListCache) -> None:
        cache.write(URL, "body")

        names = [p.name for p in cache.directory.iterdir()]
        assert names == [cache.path_for(URL).name]

    def test_unwritable_directory_is_survivable(self, tmp_path) -> None:
        """A broken cache degrades to 'always fetch', never to an exception."""
        blocker = tmp_path / "lists"
        blocker.write_text("not a directory")
        cache = ListCache(blocker, fresh_seconds=DAY, max_age_seconds=MONTH)

        cache.write(URL, "body")  # must not raise

        assert cache.read_fresh(URL) is None
        assert cache.check_writable() is False

    def test_check_writable_leaves_nothing_behind(self, cache: ListCache) -> None:
        assert cache.check_writable() is True
        assert list(cache.directory.iterdir()) == []

    def test_future_timestamp_is_not_fresh(self, cache: ListCache) -> None:
        """A clock that stepped back must not freeze the list until it catches up."""
        cache.write(URL, "body")
        age_file(cache, URL, -90 * DAY)  # stamped three months ahead

        assert cache.read_fresh(URL) is None
        assert cache.read_stale(URL) is None

        cache.prune()
        assert not cache.path_for(URL).exists()

    def test_prune_sweeps_leaked_temp_files(self, cache: ListCache) -> None:
        """Only a SIGKILL mid-write leaks one, but nothing else would remove it."""
        cache.write(URL, "body")
        leaked = cache.directory / ".tmp-abandoned"
        leaked.write_text("half a list")
        stamp = time.time() - 2 * 60 * 60
        os.utime(leaked, (stamp, stamp))
        in_flight = cache.directory / ".tmp-inflight"
        in_flight.write_text("another writer, right now")

        cache.prune()

        assert not leaked.exists()
        assert in_flight.exists()
        assert cache.path_for(URL).exists()


class TestCachedFetch:
    """TemplateProcessor.fetch_list_text — cache first, network second."""

    @pytest.fixture
    def http_client(self) -> AsyncMock:
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def cache(self, tmp_path) -> ListCache:
        return ListCache(tmp_path / "lists", fresh_seconds=DAY, max_age_seconds=MONTH)

    @pytest.fixture
    def processor(self, http_client: AsyncMock, cache: ListCache) -> TemplateProcessor:
        return TemplateProcessor(http_client, list_cache=cache)

    @staticmethod
    def ok_response(text: str, status_code: int = 200) -> AsyncMock:
        response = AsyncMock()
        response.status_code = status_code
        response.text = text
        response.raise_for_status = Mock()
        return response

    @staticmethod
    def rate_limited_response() -> AsyncMock:
        response = AsyncMock()
        response.status_code = 429
        response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "429", request=Mock(), response=Mock(status_code=429)
            )
        )
        return response

    @pytest.mark.asyncio
    async def test_fetch_stores_the_body(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        http_client.get.return_value = self.ok_response("body")

        assert await processor.fetch_list_text(URL) == "body"

        cached = cache.read_fresh(URL)
        assert cached is not None and cached.text == "body"

    @pytest.mark.asyncio
    async def test_fresh_copy_skips_the_network(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        """Younger than a day: serve it, do not ask upstream at all."""
        cache.write(URL, "cached body")

        assert await processor.fetch_list_text(URL) == "cached body"
        http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_stale_copy_is_refreshed(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        cache.write(URL, "old body")
        age_file(cache, URL, DAY + 60)
        http_client.get.return_value = self.ok_response("new body")

        assert await processor.fetch_list_text(URL) == "new body"
        http_client.get.assert_called_once()

        cached = cache.read_fresh(URL)
        assert cached is not None and cached.text == "new body"

    @pytest.mark.asyncio
    async def test_failed_refresh_falls_back_to_the_cache(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        """This is the 2026-08-17 raw.githubusercontent 429, and it must not 502."""
        cache.write(URL, "old body")
        age_file(cache, URL, DAY + 60)
        http_client.get.return_value = self.rate_limited_response()

        assert await processor.fetch_list_text(URL) == "old body"

    @pytest.mark.asyncio
    async def test_expired_copy_does_not_rescue_a_failure(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        """Past the expiry window there is nothing to serve — fail the request."""
        cache.write(URL, "ancient body")
        age_file(cache, URL, MONTH + 60)
        http_client.get.return_value = self.rate_limited_response()

        with pytest.raises(ListFetchError) as exc_info:
            await processor.fetch_list_text(URL)

        assert exc_info.value.url == URL

    @pytest.mark.asyncio
    async def test_failure_without_any_cache_raises(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        http_client.get.side_effect = httpx.ReadTimeout("timed out")

        with pytest.raises(ListFetchError) as exc_info:
            await processor.fetch_list_text(URL)

        assert exc_info.value.is_timeout
        assert http_client.get.call_count == LIST_ATTEMPTS

    @pytest.mark.asyncio
    async def test_repeated_failure_is_not_retried_immediately(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        """During an outage the endpoint must stay fast, not re-probe every time."""
        cache.write(URL, "old body")
        age_file(cache, URL, DAY + 60)
        http_client.get.return_value = self.rate_limited_response()

        assert await processor.fetch_list_text(URL) == "old body"
        calls_after_first = http_client.get.call_count

        assert await processor.fetch_list_text(URL) == "old body"
        assert http_client.get.call_count == calls_after_first

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code,body", [(200, "   \n"), (206, "1.2.3.0/24")])
    async def test_incomplete_body_is_not_cached(
        self,
        processor: TemplateProcessor,
        http_client: AsyncMock,
        cache: ListCache,
        status_code: int,
        body: str,
    ) -> None:
        """An empty 200 or a 206 must not overwrite the last good copy.

        Both pass raise_for_status, and caching one would pin the truncation for
        a day and keep it as the fallback for a month.
        """
        cache.write(URL, "good body")
        age_file(cache, URL, DAY + 60)
        http_client.get.return_value = self.ok_response(body, status_code=status_code)

        assert await processor.fetch_list_text(URL) == "good body"

        cached = cache.read_stale(URL)
        assert cached is not None and cached.text == "good body"

    @pytest.mark.asyncio
    async def test_success_clears_the_failure_backoff(
        self,
        processor: TemplateProcessor,
        http_client: AsyncMock,
        cache: ListCache,
        monkeypatch,
    ) -> None:
        """A recovered upstream must not leave a failure recorded behind it."""
        from src import processor as processor_module

        monkeypatch.setattr(processor_module, "LIST_FAILURE_BACKOFF", 0.0)
        cache.write(URL, "old body")
        age_file(cache, URL, DAY + 60)
        http_client.get.return_value = self.rate_limited_response()

        assert await processor.fetch_list_text(URL) == "old body"
        assert URL in processor_module._failed_until
        assert URL in processor_module._failed_reason

        http_client.get.return_value = self.ok_response("new body")

        assert await processor.fetch_list_text(URL) == "new body"
        assert URL not in processor_module._failed_until
        assert URL not in processor_module._failed_reason

    @pytest.mark.asyncio
    async def test_own_lists_are_refetched_within_the_minute(
        self, http_client: AsyncMock, cache: ListCache, monkeypatch
    ) -> None:
        """Hand-edited lists we publish must not take a day to reach clients."""
        from src.config import settings

        monkeypatch.setattr(settings, "list_cache_own_hosts", "s.example.com")
        processor = TemplateProcessor(http_client, list_cache=cache)
        own = "https://s.example.com/lists/telegram.list"

        cache.write(own, "old body")
        age_file(cache, own, 5 * 60)  # minutes old: stale for us, fresh for a CDN
        http_client.get.return_value = self.ok_response("new body")

        assert await processor.fetch_list_text(own) == "new body"

        cache.write(URL, "third party body")
        age_file(cache, URL, 5 * 60)
        http_client.get.reset_mock()
        assert await processor.fetch_list_text(URL) == "third party body"
        http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_queued_requests_do_not_each_retry_a_failing_list(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        """The failure twin of single-flight, and the whole point of the backoff.

        Everyone who queues on the lock while the leader is inside its
        LIST_ATTEMPTS * LIST_TIMEOUT failure would otherwise run that same cycle
        again, serialized — during an outage that is unbounded queue growth.
        """
        cache.write(URL, "old body")
        age_file(cache, URL, DAY + 60)

        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_failing_get(*args, **kwargs):
            started.set()
            await release.wait()
            raise httpx.ReadTimeout("timed out")

        http_client.get.side_effect = slow_failing_get

        leader = asyncio.create_task(processor.fetch_list_text(URL))
        await started.wait()
        queued = [asyncio.create_task(processor.fetch_list_text(URL)) for _ in range(3)]
        await asyncio.sleep(0)
        release.set()

        assert await leader == "old body"
        assert [await task for task in queued] == ["old body"] * 3
        assert http_client.get.call_count == LIST_ATTEMPTS

    @pytest.mark.asyncio
    async def test_queued_requests_fail_fast_with_an_empty_cache(
        self, processor: TemplateProcessor, http_client: AsyncMock
    ) -> None:
        """Nothing on disk: still one retry cycle total, not one per request."""
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_failing_get(*args, **kwargs):
            started.set()
            await release.wait()
            raise httpx.ReadTimeout("timed out")

        http_client.get.side_effect = slow_failing_get

        tasks = [asyncio.create_task(processor.fetch_list_text(URL))]
        await started.wait()
        tasks += [asyncio.create_task(processor.fetch_list_text(URL)) for _ in range(3)]
        await asyncio.sleep(0)
        release.set()

        for task in tasks:
            with pytest.raises(ListFetchError) as exc_info:
                await task
            # The reason survives the backoff, so the handler still answers 504.
            assert exc_info.value.is_timeout
        assert http_client.get.call_count == LIST_ATTEMPTS

    @pytest.mark.asyncio
    async def test_concurrent_refresh_fetches_once(
        self, processor: TemplateProcessor, http_client: AsyncMock, cache: ListCache
    ) -> None:
        """A TTL expiry must not send one request upstream per client."""
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_get(*args, **kwargs):
            started.set()
            await release.wait()
            return self.ok_response("new body")

        http_client.get.side_effect = slow_get

        first = asyncio.create_task(processor.fetch_list_text(URL))
        await started.wait()
        second = asyncio.create_task(processor.fetch_list_text(URL))
        await asyncio.sleep(0)  # let the second task reach the lock
        release.set()

        assert await first == "new body"
        assert await second == "new body"
        assert http_client.get.call_count == 1
