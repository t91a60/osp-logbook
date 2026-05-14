"""Tests for backend/infrastructure/repositories/vehicles.py."""

from unittest.mock import MagicMock, patch

from backend.domain.exceptions import ForbiddenError, NotFoundError
from backend.infrastructure.repositories.vehicles import VehicleRepository


class TestVehicleRepositoryDelete:
    @patch('backend.infrastructure.repositories.vehicles.VehicleRepository.has_linked_rows')
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_delete_success(self, mock_get_db, mock_get_cursor, mock_has_linked_rows, app):
        repo = VehicleRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.side_effect = [{'id': 1}]
        mock_has_linked_rows.return_value = False

        with app.test_request_context():
            repo.delete(42)

        mock_conn.commit.assert_called_once()
        assert mock_cur.execute.call_count == 2

    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_delete_not_found(self, mock_get_db, mock_get_cursor, app):
        repo = VehicleRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with app.test_request_context():
            try:
                repo.delete(42)
            except NotFoundError:
                pass
            else:
                raise AssertionError('NotFoundError not raised')

        mock_conn.rollback.assert_called_once()

    @patch('backend.infrastructure.repositories.vehicles.VehicleRepository.has_linked_rows')
    @patch('backend.infrastructure.repositories.vehicles.get_cursor')
    @patch('backend.infrastructure.repositories.vehicles.get_db')
    def test_delete_forbidden_when_linked_rows_exist(self, mock_get_db, mock_get_cursor, mock_has_linked_rows, app):
        repo = VehicleRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.side_effect = [{'id': 1}]
        mock_has_linked_rows.return_value = True

        with app.test_request_context():
            try:
                repo.delete(42)
            except ForbiddenError:
                pass
            else:
                raise AssertionError('ForbiddenError not raised')

        mock_conn.rollback.assert_called_once()
