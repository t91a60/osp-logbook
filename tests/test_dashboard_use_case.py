"""
Unit tests for GetDashboardUseCase in backend/application/dashboard.py.

Tests use an injected mock DashboardRepositoryProtocol — no Flask client, no DB.
The _build_card static method is also tested directly.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.application.dashboard import (
    DashboardResult,
    DashboardStats,
    GetDashboardUseCase,
    VehicleCard,
)


class TestDashboardResultStructure:
    def test_dashboard_result_is_frozen_dataclass(self, mock_dashboard_repo):
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        result = uc.execute_instance()
        assert isinstance(result, DashboardResult)
        assert isinstance(result.vehicle_cards, list)
        assert isinstance(result.stats, DashboardStats)

    def test_result_is_immutable(self, mock_dashboard_repo):
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        result = uc.execute_instance()
        with pytest.raises((AttributeError, TypeError)):
            result.stats = DashboardStats(trips=0, fuel=0, maintenance=0)  # type: ignore[misc]

    def test_generated_on_is_today_iso(self, mock_dashboard_repo):
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        result = uc.execute_instance()
        assert result.generated_on == date.today().isoformat()


class TestVehicleCardDaysAgo:
    def test_vehicle_card_days_ago_computed_correctly(self, mock_dashboard_repo):
        mock_dashboard_repo.get_vehicle_cards.return_value = [
            {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001',
             'type': 'GBA', 'last_km': 37500, 'last_trip_date': '2026-05-01'}
        ]
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        with patch('backend.application.dashboard.date') as mock_date:
            mock_date.today.return_value = date(2026, 5, 12)
            mock_date.fromisoformat.side_effect = date.fromisoformat
            result = uc.execute_instance()
        assert result.vehicle_cards[0].days_ago == 11

    def test_vehicle_card_no_trip_date_has_none_days_ago(self, mock_dashboard_repo):
        mock_dashboard_repo.get_vehicle_cards.return_value = [
            {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001',
             'type': 'GBA', 'last_km': None, 'last_trip_date': None}
        ]
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        result = uc.execute_instance()
        assert result.vehicle_cards[0].days_ago is None


class TestDashboardStats:
    def test_stats_aggregated_correctly(self, mock_dashboard_repo):
        mock_dashboard_repo.get_aggregate_stats.return_value = {
            'trips': 5, 'fuel': 3, 'maintenance': 1
        }
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        result = uc.execute_instance()
        assert result.stats.trips == 5
        assert result.stats.fuel == 3
        assert result.stats.maintenance == 1

    def test_empty_vehicle_list_returns_empty_cards(self, mock_dashboard_repo):
        mock_dashboard_repo.get_vehicle_cards.return_value = []
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        result = uc.execute_instance()
        assert result.vehicle_cards == []

    def test_repo_methods_called_once(self, mock_dashboard_repo):
        uc = GetDashboardUseCase(dashboard_repo=mock_dashboard_repo)
        uc.execute_instance()
        mock_dashboard_repo.get_vehicle_cards.assert_called_once()
        mock_dashboard_repo.get_recent_trips.assert_called_once()
        mock_dashboard_repo.get_recent_fuel.assert_called_once()
        mock_dashboard_repo.get_aggregate_stats.assert_called_once()


class TestBuildCardStatic:
    def test_positive_days_ago(self):
        row = {'id': 1, 'name': 'X', 'plate': 'P', 'type': 'T',
               'last_km': 100, 'last_trip_date': '2026-05-01'}
        today = date(2026, 5, 12)
        card = GetDashboardUseCase._build_card(row, today)
        assert card.days_ago == 11

    def test_no_last_trip_date(self):
        row = {'id': 1, 'name': 'X', 'plate': 'P', 'type': 'T',
               'last_km': None, 'last_trip_date': None}
        card = GetDashboardUseCase._build_card(row, date.today())
        assert card.days_ago is None
        assert card.last_trip_date is None

    def test_result_is_frozen(self):
        row = {'id': 1, 'name': 'X', 'plate': 'P', 'type': 'T',
               'last_km': 50, 'last_trip_date': None}
        card = GetDashboardUseCase._build_card(row, date.today())
        with pytest.raises((AttributeError, TypeError)):
            card.name = 'changed'  # type: ignore[misc]
