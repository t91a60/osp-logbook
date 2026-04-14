"""Tests for backend/services/core_service.py — internal helper functions."""

import pytest


class TestToInt:
    """Test the _to_int helper in core_service."""

    def test_valid_int(self):
        from backend.services.core_service import _to_int
        assert _to_int(5) == 5
        assert _to_int('10') == 10

    def test_none_returns_none(self):
        from backend.services.core_service import _to_int
        assert _to_int(None) is None

    def test_empty_string_returns_none(self):
        from backend.services.core_service import _to_int
        assert _to_int('') is None

    def test_invalid_raises(self):
        from backend.services.core_service import _to_int
        with pytest.raises(ValueError):
            _to_int('abc')

    def test_float_string_raises(self):
        from backend.services.core_service import _to_int
        with pytest.raises(ValueError):
            _to_int('3.14')


class TestToFloat:
    """Test the _to_float helper in core_service."""

    def test_valid_float(self):
        from backend.services.core_service import _to_float
        assert _to_float(3.14) == pytest.approx(3.14)
        assert _to_float('2.5') == pytest.approx(2.5)

    def test_int_value(self):
        from backend.services.core_service import _to_float
        assert _to_float(5) == pytest.approx(5.0)
        assert _to_float('10') == pytest.approx(10.0)

    def test_none_returns_none(self):
        from backend.services.core_service import _to_float
        assert _to_float(None) is None

    def test_empty_string_returns_none(self):
        from backend.services.core_service import _to_float
        assert _to_float('') is None

    def test_invalid_raises(self):
        from backend.services.core_service import _to_float
        with pytest.raises(ValueError):
            _to_float('not-a-number')
