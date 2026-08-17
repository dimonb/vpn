"""Shared fixtures."""

import pytest

from src import processor as processor_module
from src.config import settings


@pytest.fixture(autouse=True)
def isolated_list_cache(tmp_path, monkeypatch):
    """Give every test its own empty list cache.

    Without this the tests would read and write the real /cache volume, and a
    body cached by one test would satisfy the next one's fetch — so mocked HTTP
    clients would go uncalled and assertions on them would fail for no visible
    reason.
    """
    monkeypatch.setattr(settings, "list_cache_dir", str(tmp_path / "lists"))
    processor_module._refresh_locks.clear()
    processor_module._failed_until.clear()
    yield
    processor_module._refresh_locks.clear()
    processor_module._failed_until.clear()
