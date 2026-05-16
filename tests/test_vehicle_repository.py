from unittest.mock import MagicMock, patch

import pytest

from backend.domain.exceptions import ForbiddenError, NotFoundError
from backend.infrastructure.repositories import vehicles
from backend.infrastructure.repositories.vehicles import VehicleRepository


class TestVehicleRepositoryGetters:
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_all_returns_rows(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_cursor.return_value = mock_cur

        rows = repo.get_all()

        assert rows == [{'id': 1, 'name': 'GBA'}]
        mock_cur.execute.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_active_returns_none_for_invalid_id(self, mock_get_db):
        repo = VehicleRepository()

        assert repo.get_active('x') is None
        assert repo.get_active(-1) is None
        mock_get_db.assert_not_called()

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_active_checks_schema_and_returns_vehicle(self, mock_get_db, mock_get_cursor, monkeypatch):
        monkeypatch.setattr(vehicles, '_vehicles_has_active_column', None)
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [{'present': 1}, {'id': 2, 'name': 'SLR'}]
        mock_get_cursor.return_value = mock_cur

        row = repo.get_active('2')

        assert row == {'id': 2, 'name': 'SLR'}
        assert mock_cur.execute.call_count == 2
        assert "COALESCE(active::text, '1')" in mock_cur.execute.call_args_list[1].args[0]
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_active_without_active_column(self, mock_get_db, mock_get_cursor, monkeypatch):
        monkeypatch.setattr(vehicles, '_vehicles_has_active_column', None)
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [None, {'id': 2}]
        mock_get_cursor.return_value = mock_cur

        row = repo.get_active(2)

        assert row == {'id': 2}
        assert 'WHERE id = %s LIMIT 1' in mock_cur.execute.call_args_list[1].args[0]
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_by_id_returns_row(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {'id': 3}
        mock_get_cursor.return_value = mock_cur

        row = repo.get_by_id(3)

        assert row == {'id': 3}
        mock_cur.close.assert_called_once()


class TestVehicleRepositoryMetrics:
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_last_km_returns_normalized_values(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {'km': 12345, 'dt': '2024-01-15'}
        mock_get_cursor.return_value = mock_cur

        km, dt = repo.get_last_km(1)

        assert km == 12345
        assert dt == '2024-01-15'
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_last_km_returns_none_when_missing(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_get_cursor.return_value = mock_cur

        km, dt = repo.get_last_km(1)

        assert (km, dt) == (None, None)

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_get_recent_drivers_returns_names(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{'driver': 'Jan'}, {'driver': 'Anna'}]
        mock_get_cursor.return_value = mock_cur

        drivers = repo.get_recent_drivers(days=30)

        assert drivers == ['Jan', 'Anna']
        mock_cur.close.assert_called_once()


class TestVehicleRepositoryMutations:
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_add_commits(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_get_cursor.return_value = mock_cur

        repo.add('GBA', 'KR123', 'gaśniczy')

        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_update_rolls_back_on_error(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')
        mock_get_cursor.return_value = mock_cur

        with pytest.raises(RuntimeError):
            repo.update(1, 'GBA', 'KR123', 'gaśniczy')

        mock_conn.rollback.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.VehicleRepository.has_linked_rows')
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_delete_raises_not_found(self, mock_get_db, mock_get_cursor, mock_has_linked):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_get_cursor.return_value = mock_cur
        mock_has_linked.return_value = False

        with pytest.raises(NotFoundError):
            repo.delete(1)

    @patch('backend.infrastructure.repositories.vehicles.VehicleRepository.has_linked_rows')
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_delete_raises_forbidden_when_linked(self, mock_get_db, mock_get_cursor, mock_has_linked):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {'id': 1}
        mock_get_cursor.return_value = mock_cur
        mock_has_linked.return_value = True

        with pytest.raises(ForbiddenError):
            repo.delete(1)

    @patch('backend.infrastructure.repositories.vehicles.VehicleRepository.has_linked_rows')
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_delete_success(self, mock_get_db, mock_get_cursor, mock_has_linked):
        repo = VehicleRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {'id': 1}
        mock_get_cursor.return_value = mock_cur
        mock_has_linked.return_value = False

        repo.delete(1)

        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_has_linked_rows_true_and_false(self, mock_get_db, mock_get_cursor):
        repo = VehicleRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.side_effect = [{'count': 2}, {'count': 0}]

        assert repo.has_linked_rows(1) is True
        assert repo.has_linked_rows(1) is False
        assert mock_cur.close.call_count == 2
