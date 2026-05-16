from unittest.mock import MagicMock, patch

from backend.infrastructure.repositories.dashboard import DashboardRepository


class TestDashboardRepository:
    def test_get_vehicle_cards_with_provided_cursor(self):
        repo = DashboardRepository()
        cur = MagicMock()
        cur.fetchall.return_value = [{'id': 1, 'name': 'GBA'}]

        result = repo.get_vehicle_cards.__wrapped__(repo, cur=cur)

        assert result == [{'id': 1, 'name': 'GBA'}]
        cur.execute.assert_called_once()

    @patch('backend.infrastructure.repositories.dashboard.get_cursor')
    @patch('backend.infrastructure.repositories.dashboard.get_db')
    def test_get_recent_trips_uses_internal_cursor(self, mock_get_db, mock_get_cursor):
        repo = DashboardRepository()
        mock_get_db.return_value = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [{'id': 11}]
        mock_get_cursor.return_value = cur

        result = repo.get_recent_trips.__wrapped__(repo, limit=2, cur=None)

        assert result == [{'id': 11}]
        assert cur.execute.call_args.args[1] == (2,)
        cur.close.assert_called_once()

    def test_get_recent_fuel_with_provided_cursor(self):
        repo = DashboardRepository()
        cur = MagicMock()
        cur.fetchall.return_value = [{'id': 21}]

        result = repo.get_recent_fuel.__wrapped__(repo, limit=4, cur=cur)

        assert result == [{'id': 21}]
        assert cur.execute.call_args.args[1] == (4,)

    def test_get_aggregate_stats_maps_nulls_to_zero(self):
        repo = DashboardRepository()
        cur = MagicMock()
        cur.fetchone.return_value = {
            'trips_count': None,
            'fuel_count': 3,
            'maint_count': None,
        }

        result = repo.get_aggregate_stats.__wrapped__(repo, cur=cur)

        assert result == {'trips': 0, 'fuel': 3, 'maintenance': 0}

    @patch('backend.infrastructure.repositories.dashboard.get_cursor')
    @patch('backend.infrastructure.repositories.dashboard.get_db')
    def test_run_with_cursor_closes_cursor(self, mock_get_db, mock_get_cursor):
        repo = DashboardRepository()
        mock_get_db.return_value = MagicMock()
        cur = MagicMock()
        mock_get_cursor.return_value = cur

        result = repo._run_with_cursor(None, lambda c: ['ok'])

        assert result == ['ok']
        cur.close.assert_called_once()

    def test_run_with_cursor_uses_provided_cursor(self):
        repo = DashboardRepository()
        cur = MagicMock()

        result = repo._run_with_cursor(cur, lambda c: {'same_cursor': c is cur})

        assert result == {'same_cursor': True}
