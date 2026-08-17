"""On-disk cache for RULE-SET / NETSET list bodies.

The lists are large, change at most once a day, and are fetched from hosts we do
not control. On 2026-08-17 `raw.githubusercontent.com` answered `429 Too Many
Requests` to the whole internet for a while, and since every single request
re-fetched every list, both RU relays served nothing but 502 for the duration.

So keep the last good copy on disk, in a volume that outlives the container:

* younger than ``fresh_seconds``  -> serve it, do not touch the network at all
* older                           -> re-fetch, and store the new body
* re-fetch failed                 -> serve the stale copy anyway, up to ``max_age_seconds``
* nothing usable on disk          -> the caller fails the request (502/504)

The file's own mtime is the timestamp — no sidecar metadata that could drift out
of sync with the body, and `ls -l` on the host tells the whole story.

Every filesystem error is swallowed and logged: a broken cache must degrade to
"fetch every time", never to a failed request.
"""

import hashlib
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# A copy stamped in the future is a clock that stepped backwards (bad boot clock,
# hypervisor migration, NTP correction), not a young copy. Clamping its age to
# zero would make it fresh forever *and* unprunable, freezing the list until the
# wall clock caught up — so distrust it instead, past this much tolerance.
CLOCK_SKEW_TOLERANCE = 60.0

# A temp file only survives a SIGKILL between mkstemp and os.replace. Rare, but
# nothing else would ever remove it, so sweep the ones that cannot be in flight.
TEMP_FILE_PREFIX = ".tmp-"
TEMP_FILE_MAX_AGE = 60 * 60


@dataclass(frozen=True)
class CachedList:
    """A list body read back from disk, with the age of the copy in seconds."""

    text: str
    age: float


class ListCache:
    """Content-addressed store of list bodies, keyed by URL."""

    def __init__(
        self, directory: str | os.PathLike, fresh_seconds: float, max_age_seconds: float
    ):
        self.directory = Path(directory)
        self.fresh_seconds = fresh_seconds
        self.max_age_seconds = max_age_seconds

    def path_for(self, key: str) -> Path:
        """Cache file for a URL. Hashed, so any URL is a valid filename."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.body"

    def read(self, key: str, max_age: float) -> CachedList | None:
        """Return the cached body when a copy no older than ``max_age`` exists."""
        path = self.path_for(key)
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return None
        if age < -CLOCK_SKEW_TOLERANCE:
            logger.warning(
                f"List cache entry is {-age / 3600:.1f}h in the future "
                f"(clock stepped back?), refetching: {key}"
            )
            return None
        age = max(0.0, age)
        if age > max_age:
            return None
        try:
            return CachedList(path.read_text(encoding="utf-8"), age)
        except OSError as e:
            logger.warning(f"List cache unreadable for {key}: {e!r}")
            return None

    def read_fresh(self, key: str) -> CachedList | None:
        """A copy young enough to serve without asking the network."""
        return self.read(key, self.fresh_seconds)

    def read_stale(self, key: str) -> CachedList | None:
        """Any copy still within the expiry window — the fallback on a failure."""
        return self.read(key, self.max_age_seconds)

    def write(self, key: str, text: str) -> None:
        """Store a body, atomically, so a crash cannot leave a truncated list."""
        path = self.path_for(key)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=self.directory, prefix=TEMP_FILE_PREFIX)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(text)
                    # Without this a power loss can leave the rename durable and
                    # the bytes not, i.e. a truncated list that looks valid for
                    # a month. Writes happen a handful of times a day; pay it.
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, path)
            except BaseException:
                # Never leave the partial file behind for prune() to age out.
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except OSError as e:
            logger.warning(f"List cache write failed for {key}: {e!r}")
            return
        self.prune()

    def check_writable(self) -> bool:
        """Probe the directory so a broken volume is visible at startup.

        Every other failure here is swallowed by design, which means a cache
        that never stores anything looks exactly like one that works — until an
        upstream outage turns into 502s that the cache was supposed to absorb.
        """
        probe = self.directory / f"{TEMP_FILE_PREFIX}probe"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as e:
            logger.error(f"List cache directory {self.directory} is unusable: {e!r}")
            return False
        return True

    def prune(self) -> None:
        """Delete bodies past the expiry window, and any leaked temp file.

        A URL dropped from a template is never asked for again, so nothing else
        would ever clean it up.
        """
        try:
            entries = list(self.directory.iterdir())
        except OSError:
            return
        now = time.time()
        for entry in entries:
            if entry.name.startswith(TEMP_FILE_PREFIX):
                max_age = TEMP_FILE_MAX_AGE
            elif entry.suffix == ".body":
                max_age = self.max_age_seconds
            else:
                continue
            try:
                # abs(): a future mtime is a broken clock, not a young file, and
                # must not make an entry immortal.
                if abs(now - entry.stat().st_mtime) > max_age:
                    entry.unlink()
                    logger.info(f"List cache expired, removed {entry.name}")
            except OSError:
                continue
