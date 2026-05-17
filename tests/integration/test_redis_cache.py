from datetime import date
import time

import pytest
import redis

from backend.infrastructure.cache.redis_cache import RedisCache


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def clear_redis(redis_url):
    client = redis.from_url(redis_url, decode_responses=True)
    client.flushdb()
    yield
    client.flushdb()


def test_set_and_get_returns_value(redis_url):
    cache = RedisCache(redis_url)
    cache.set("key1", "hello", ttl_seconds=60)
    assert cache.get("key1") == "hello"


def test_get_missing_key_returns_none(redis_url):
    cache = RedisCache(redis_url)
    assert cache.get("does_not_exist") is None


def test_set_with_ttl_expires(redis_url):
    cache = RedisCache(redis_url)
    cache.set("expiring", "value", ttl_seconds=1)
    time.sleep(1.1)
    assert cache.get("expiring") is None


def test_invalidate_tags_removes_all_tagged_keys(redis_url):
    cache = RedisCache(redis_url)
    cache.set("a", 1, ttl_seconds=60, tags=["group1"])
    cache.set("b", 2, ttl_seconds=60, tags=["group1"])
    cache.set("c", 3, ttl_seconds=60, tags=["group2"])
    cache.invalidate_tags(["group1"])
    assert cache.get("a") is None
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_invalidate_prefix_removes_matching_keys(redis_url):
    cache = RedisCache(redis_url)
    cache.set("vehicles:1", "v1", ttl_seconds=60)
    cache.set("vehicles:2", "v2", ttl_seconds=60)
    cache.set("dashboard:x", "d", ttl_seconds=60)
    cache.invalidate_prefix("vehicles:")
    assert cache.get("vehicles:1") is None
    assert cache.get("vehicles:2") is None
    assert cache.get("dashboard:x") == "d"


def test_set_complex_object_serialises(redis_url):
    cache = RedisCache(redis_url)
    payload = {"date": date.today(), "count": 42, "items": [1, 2, 3]}
    cache.set("complex", payload, ttl_seconds=60)
    result = cache.get("complex")
    assert result["count"] == 42
    assert result["items"] == [1, 2, 3]
    assert isinstance(result["date"], str)


def test_pipeline_atomic_set_writes_tag_index(redis_url):
    cache = RedisCache(redis_url)
    cache.set("atomic_key", "val", ttl_seconds=60, tags=["t1"])
    tagged_keys = cache.redis.smembers("tag:t1")
    assert "atomic_key" in tagged_keys


def test_lru_eviction_when_max_entries_reached_in_memory_fallback(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = RedisCache(url=None)
    cache._MAX_SIZE = 5

    for i in range(7):
        cache.set(f"lru_{i}", i, ttl_seconds=300)

    remaining = sum(1 for i in range(7) if cache.get(f"lru_{i}") is not None)
    assert remaining <= 5


def test_in_memory_invalidate_tags_and_prefix(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = RedisCache(url=None)
    cache.set("report:1", {"a": 1}, ttl_seconds=60, tags=["report"])
    cache.set("report:2", {"b": 2}, ttl_seconds=60, tags=["report"])
    cache.set("dashboard:1", {"c": 3}, ttl_seconds=60, tags=["dashboard"])

    cache.invalidate_tags(["report"])
    assert cache.get("report:1") is None
    assert cache.get("report:2") is None
    assert cache.get("dashboard:1") == {"c": 3}

    cache.invalidate_prefix("dashboard:")
    assert cache.get("dashboard:1") is None


def test_redis_connection_errors_fall_back_to_in_memory(monkeypatch):
    class FailingRedis:
        def get(self, _key):
            raise redis.ConnectionError("boom")

        def pipeline(self):
            raise redis.ConnectionError("boom")

        def scan(self, *args, **kwargs):
            raise redis.ConnectionError("boom")

        def smembers(self, _key):
            raise redis.ConnectionError("boom")

    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = RedisCache(url=None)
    cache.redis = FailingRedis()

    cache.set("k", "v", ttl_seconds=60, tags=["t"])
    assert cache.get("k") == "v"

    cache.invalidate_tags(["t"])
    assert cache.get("k") is None

    cache.set("prefix:1", "x", ttl_seconds=60)
    cache.invalidate_prefix("prefix:")
    assert cache.get("prefix:1") is None


def test_set_fallback_keeps_unserializable_values(monkeypatch):
    class Unserializable:
        pass

    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = RedisCache(url=None)
    obj = Unserializable()
    cache.set("obj", obj, ttl_seconds=60)
    assert cache.get("obj") is obj
