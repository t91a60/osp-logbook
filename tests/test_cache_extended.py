"""Tests for cache_service — get_vehicles_cached, FIFO eviction, and edge cases."""
import threading
import time

import pytest

pytest.importorskip("redis")

from backend.services import cache_service


class TestGetVehiclesCached:
    @pytest.fixture(autouse=True)
    def _clear(self):
        cache_service.invalidate_prefix("vehicles:all")

    def test_calls_get_or_set_with_correct_key(self):
        call_count = 0

        def fake_loader():
            nonlocal call_count
            call_count += 1
            return [{"id": 1, "name": "Fiat Ducato"}]

        result = cache_service.get_or_set("vehicles:all", 60, fake_loader)
        assert call_count == 1
        assert result == [{"id": 1, "name": "Fiat Ducato"}]

        result = cache_service.get_or_set("vehicles:all", 60, fake_loader)
        assert result == [{"id": 1, "name": "Fiat Ducato"}]
        assert call_count == 1

    def test_returns_empty_list_when_no_vehicles(self):
        result = cache_service.get_or_set("vehicles:all", 60, lambda: [])
        assert result == []


class TestCacheFIFOEviction:
    @pytest.fixture(autouse=True)
    def _clear(self):
        cache_service.invalidate_prefix("")

    def test_evicts_oldest_when_full(self):
        original_max = cache_service.cache._MAX_SIZE
        try:
            cache_service.cache._MAX_SIZE = 5
            for i in range(7):
                cache_service.get_or_set(f"key{i}", 60, lambda i=i: f"val{i}")

            assert len(cache_service.cache._cache) <= 5
            assert cache_service.cache.get("key0") is None
            assert cache_service.cache.get("key1") is None
            assert cache_service.cache.get("key6") == "val6"
            assert cache_service.cache.get("key5") == "val5"
        finally:
            cache_service.cache._MAX_SIZE = original_max


class TestCacheGetOrSetEdgeCases:
    @pytest.fixture(autouse=True)
    def _clear(self):
        cache_service.invalidate_prefix("")

    def test_loader_exception_propagates(self):
        def bad_loader():
            raise RuntimeError("DB down")

        with pytest.raises(RuntimeError, match="DB down"):
            cache_service.get_or_set("failing", 60, bad_loader)

    def test_negative_ttl_treated_as_one_second(self):
        cache_service.get_or_set("neg_ttl", 1, lambda: "val")
        entry = cache_service.cache._cache.get("neg_ttl")
        assert entry is not None

    def test_move_to_end_on_hit(self):
        cache_service.get_or_set("first", 60, lambda: "a")
        cache_service.get_or_set("second", 60, lambda: "b")
        cache_service.get_or_set("third", 60, lambda: "c")

        cache_service.get_or_set("first", 60, lambda: "WRONG")

        keys = list(cache_service.cache._cache.keys())
        assert keys[-1] == "first"

    def test_zero_value_cached(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return 0

        assert cache_service.get_or_set("zero", 60, loader) == 0
        assert cache_service.get_or_set("zero", 60, loader) == 0
        assert call_count == 1

    def test_false_value_cached(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return False

        assert cache_service.get_or_set("false", 60, loader) is False
        assert cache_service.get_or_set("false", 60, loader) is False
        assert call_count == 1

    def test_empty_string_value_cached(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return ""

        assert cache_service.get_or_set("empty", 60, loader) == ""
        assert cache_service.get_or_set("empty", 60, loader) == ""
        assert call_count == 1
