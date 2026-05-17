import importlib

import pytest
import redis


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def clear_redis(redis_url):
    client = redis.from_url(redis_url, decode_responses=True)
    client.flushdb()
    yield
    client.flushdb()


def test_get_or_set_calls_loader_once_then_caches(redis_url, monkeypatch):
    monkeypatch.setenv("REDIS_URL", redis_url)
    from backend.services import cache_service

    importlib.reload(cache_service)

    call_count = 0

    def loader():
        nonlocal call_count
        call_count += 1
        return {"data": "value"}

    first = cache_service.get_or_set("test:singleton", ttl_seconds=60, loader=loader)
    second = cache_service.get_or_set("test:singleton", ttl_seconds=60, loader=loader)

    assert first == second
    assert call_count == 1


def test_invalidate_prefix_clears_matching_cached_values(redis_url, monkeypatch):
    monkeypatch.setenv("REDIS_URL", redis_url)
    from backend.services import cache_service

    importlib.reload(cache_service)

    cache_service.get_or_set("dashboard:v1", ttl_seconds=60, loader=lambda: "dash")
    cache_service.get_or_set("vehicles:all", ttl_seconds=60, loader=lambda: "veh")

    cache_service.invalidate_prefix("dashboard:")

    result = cache_service.get_or_set("vehicles:all", ttl_seconds=60, loader=lambda: "MISS")
    assert result == "veh"
