"""
Unit tests for backend/application/dashboard.py — GetDashboardUseCase.

All tests mock get_db / get_cursor to avoid a real PostgreSQL connection.
"""
from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

from backend.application.dashboard import (
    GetDashboardUseCase,
    DashboardResult,
    VehicleCard,
    DashboardStats,
)


def _make_cursor(vehicles=None, recent_trips=None, recent_fuel=None, stats_row=None):
    """Build a MagicMock cursor with pre-configured fetchall/fetchone side effects."""
    cur = MagicMock()
    cur.fetchall.side_effect = [
        vehicles or [],
        recent_trips or [],
        recent_fuel or [],
    ]
    cur.fetchone.return_value = stats_row or {
        'trips_count': 0,
        'fuel_count': 0,
        'maint_count': 0,
    }
    return cur


class TestGetDashboardUseCaseExecute:
    @patch('backend.application.dashboard.get_cursor')
    @patch('backend.application.dashboard.get_db')
    def test_returns_dashboard_result(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = _make_cursor()
        mock_get_cursor.return_value = mock_cur

        result = GetDashboardUseCase.execute()

        assert isinstance(result, DashboardResult)
        assert result.vehicle_cards == []
        assert result.recent_trips == []
        assert result.recent_fuel == []
        assert isinstance(result.stats, DashboardStats)
        assert result.generated_on == date.today().isoformat()
        mock_cur.close.assert_called_once()

    @patch('backend.application.dashboard.get_cursor')
    @patch('backend.application.dashboard.get_db')
    def test_closes_cursor_on_exception(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.execute.side_effect = RuntimeError('db boom')

        with pytest.raises(RuntimeError):
            GetDashboardUseCase.execute()

        mock_cur.close.assert_called_once()

    @patch('backend.application.dashboard.get_cursor')
    @patch('backend.application.dashboard.get_db')
    def test_vehicle_cards_built_correctly(self, mock_get_db, mock_get_cursor):
        today = date.today()
        mock_get_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            vehicles=[{
                'id': 1, 'name': 'GBA', 'plate': 'KR001',
                'type': 'gaśniczy', 'last_km': 12345,
                'last_trip_date': today.isoformat(),
            }],
            stats_row={'trips_count': 3, 'fuel_count': 2, 'maint_count': 1},
        )
        mock_get_cursor.return_value = mock_cur

        result = GetDashboardUseCase.execute()

        assert len(result.vehicle_cards) == 1
        card = result.vehicle_cards[0]
        assert isinstance(card, VehicleCard)
        assert card.id == 1
        assert card.name == 'GBA'
        assert card.last_km == 12345
        assert card.days_ago == 0

    @patch('backend.application.dashboard.get_cursor')
    @patch('backend.application.dashboard.get_db')
    def test_vehicle_card_broken_date_gives_none_days_ago(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = _make_cursor(vehicles=[{
            'id': 2, 'name': 'SLR', 'plate': 'KR002',
            'type': 'ratowniczy', 'last_km': None,
            'last_trip_date': 'not-a-date',
        }])
        mock_get_cursor.return_value = mock_cur

        result = GetDashboardUseCase.execute()

        card = result.vehicle_cards[0]
        assert card.days_ago is None

    @patch('backend.application.dashboard.get_cursor')
    @patch('backend.application.dashboard.get_db')
    def test_stats_populated(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            stats_row={'trips_count': 10, 'fuel_count': 5, 'maint_count': 3}
        )
        mock_get_cursor.return_value = mock_cur

        result = GetDashboardUseCase.execute()

        assert result.stats.trips == 10
        assert result.stats.fuel == 5
        assert result.stats.maintenance == 3

    @patch('backend.application.dashboard.get_cursor')
    @patch('backend.application.dashboard.get_db')
    def test_executes_four_queries(self, mock_get_db, mock_get_cursor):
        """Verifies the CTE + 3 follow-up queries are issued."""
        mock_get_db.return_value = MagicMock()
        mock_cur = _make_cursor()
        mock_get_cursor.return_value = mock_cur

        GetDashboardUseCase.execute()

        # 1 CTE (vehicles), 1 recent_trips, 1 recent_fuel, 1 stats
        assert mock_cur.execute.call_count == 4


class TestGetDashboardBuildCard:
    def test_positive_days_ago(self):
        from datetime import timedelta
        today = date.today()
        past = (today - timedelta(days=7)).isoformat()
        row = {'id': 1, 'name': 'X', 'plate': 'P', 'type': 'T',
               'last_km': 100, 'last_trip_date': past}
        card = GetDashboardUseCase._build_card(row, today)
        assert card.days_ago == 7

    def test_no_last_trip_date(self):
        today = date.today()
        row = {'id': 1, 'name': 'X', 'plate': 'P', 'type': 'T',
               'last_km': None, 'last_trip_date': None}
        card = GetDashboardUseCase._build_card(row, today)
        assert card.days_ago is None
        assert card.last_trip_date is None

    def test_result_is_frozen(self):
        today = date.today()
        row = {'id': 1, 'name': 'X', 'plate': 'P', 'type': 'T',
               'last_km': 50, 'last_trip_date': None}
        card = GetDashboardUseCase._build_card(row, today)
        with pytest.raises((AttributeError, TypeError)):
            card.name = 'changed'  # type: ignore[misc]
