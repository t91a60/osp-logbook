"""Tests for backend/helpers.py — pure utility functions and decorators."""

from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest

from backend.helpers import (
    parse_positive_int,
    normalize_iso_date,
    days_since_iso_date,
    build_date_where,
    login_required,
    admin_required,
)


# ---------------------------------------------------------------------------
# parse_positive_int
# ---------------------------------------------------------------------------
class TestParsePositiveInt:
    def test_valid_positive(self):
        assert parse_positive_int('5') == 5
        assert parse_positive_int(10) == 10

    def test_zero_returns_default(self):
        assert parse_positive_int(0) == 1
        assert parse_positive_int('0', default=7) == 7

    def test_negative_returns_default(self):
        assert parse_positive_int(-3) == 1
        assert parse_positive_int('-10', default=2) == 2

    def test_none_returns_default(self):
        assert parse_positive_int(None) == 1
        assert parse_positive_int(None, default=99) == 99

    def test_non_numeric_string_returns_default(self):
        assert parse_positive_int('abc') == 1
        assert parse_positive_int('', default=5) == 5

    def test_float_string_returns_default(self):
        assert parse_positive_int('3.5') == 1

    def test_custom_default(self):
        assert parse_positive_int(None, default=42) == 42


# ---------------------------------------------------------------------------
# normalize_iso_date
# ---------------------------------------------------------------------------
class TestNormalizeIsoDate:
    def test_none_returns_none(self):
        assert normalize_iso_date(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_iso_date('') is None

    def test_whitespace_only_returns_none(self):
        assert normalize_iso_date('   ') is None

    def test_date_object(self):
        assert normalize_iso_date(date(2024, 3, 15)) == '2024-03-15'

    def test_datetime_object(self):
        assert normalize_iso_date(datetime(2024, 3, 15, 10, 30)) == '2024-03-15'

    def test_iso_string(self):
        assert normalize_iso_date('2024-03-15') == '2024-03-15'

    def test_iso_datetime_string_with_T(self):
        assert normalize_iso_date('2024-03-15T10:30:00') == '2024-03-15'

    def test_datetime_string_with_space(self):
        assert normalize_iso_date('2024-03-15 10:30:00') == '2024-03-15'

    def test_invalid_date_returns_none(self):
        assert normalize_iso_date('not-a-date') is None
        assert normalize_iso_date('2024-13-01') is None

    def test_integer_value_returns_none(self):
        # str(123) = '123', which is not a valid date
        assert normalize_iso_date(123) is None


# ---------------------------------------------------------------------------
# days_since_iso_date
# ---------------------------------------------------------------------------
class TestDaysSinceIsoDate:
    def test_today_returns_zero(self):
        today = date.today()
        assert days_since_iso_date(today.isoformat()) == 0

    def test_past_date(self):
        ref = date(2024, 6, 15)
        assert days_since_iso_date('2024-06-10', today=ref) == 5

    def test_future_date_returns_negative(self):
        ref = date(2024, 6, 10)
        assert days_since_iso_date('2024-06-15', today=ref) == -5

    def test_none_returns_none(self):
        assert days_since_iso_date(None) is None

    def test_invalid_date_returns_none(self):
        assert days_since_iso_date('bad') is None

    def test_with_datetime_object(self):
        ref = date(2024, 6, 15)
        assert days_since_iso_date(datetime(2024, 6, 10, 12, 0), today=ref) == 5


# ---------------------------------------------------------------------------
# build_date_where
# ---------------------------------------------------------------------------
class TestBuildDateWhere:
    def test_ten_okres(self):
        parts, params = build_date_where('ten', None, None)
        assert len(parts) == 1
        assert 'BETWEEN' in parts[0]
        assert len(params) == 2
        # First param should be first day of current month
        today = date.today()
        assert params[0] == today.replace(day=1).isoformat()
        assert params[1] == today.isoformat()

    def test_poprzedni_okres(self):
        parts, params = build_date_where('poprzedni', None, None)
        assert len(parts) == 1
        assert 'BETWEEN' in parts[0]
        assert len(params) == 2

    def test_custom_range_both(self):
        parts, params = build_date_where(None, '2024-01-01', '2024-01-31')
        assert len(parts) == 2
        assert any('>=' in p for p in parts)
        assert any('<=' in p for p in parts)
        assert params == ['2024-01-01', '2024-01-31']

    def test_custom_range_only_from(self):
        parts, params = build_date_where(None, '2024-01-01', None)
        assert len(parts) == 1
        assert '>=' in parts[0]
        assert params == ['2024-01-01']

    def test_custom_range_only_to(self):
        parts, params = build_date_where(None, None, '2024-01-31')
        assert len(parts) == 1
        assert '<=' in parts[0]
        assert params == ['2024-01-31']

    def test_no_filters(self):
        parts, params = build_date_where(None, None, None)
        assert parts == []
        assert params == []

    def test_custom_alias(self):
        parts, _ = build_date_where('ten', None, None, alias='f')
        assert 'f.date' in parts[0]

    def test_default_alias(self):
        parts, _ = build_date_where('ten', None, None)
        assert 't.date' in parts[0]


# ---------------------------------------------------------------------------
# login_required decorator
# ---------------------------------------------------------------------------
class TestLoginRequired:
    def test_redirects_when_not_logged_in(self, client):
        """GET to a login_required route without session redirects to login."""
        # The dashboard route requires login
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    @patch('backend.routes.main.get_or_set')
    @patch('backend.routes.main.get_cursor')
    @patch('backend.routes.main.get_db')
    def test_allows_access_when_logged_in(self, mock_get_db, mock_get_cursor, mock_cache, authenticated_client):
        """GET to dashboard with an authenticated session does not redirect to login."""
        # Mock cache to return a pre-built dashboard payload
        mock_cache.return_value = {
            'vehicle_cards': [],
            'recent_trips': [],
            'recent_fuel': [],
            'stats': {'trips': 0, 'fuel': 0, 'maintenance': 0},
        }

        response = authenticated_client.get('/')
        # Should NOT redirect to /login
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# admin_required decorator
# ---------------------------------------------------------------------------
class TestAdminRequired:
    def test_redirects_when_not_logged_in(self, client):
        """Non-authenticated user is redirected to login."""
        response = client.get('/pojazdy')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    def test_403_when_not_admin(self, authenticated_client):
        """Authenticated but non-admin user gets 403."""
        response = authenticated_client.get('/pojazdy')
        assert response.status_code == 403

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_allows_admin_access(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin user gets through (route handler executes, not blocked by decorator)."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        response = admin_client.get('/pojazdy')
        assert response.status_code not in (302, 403)
