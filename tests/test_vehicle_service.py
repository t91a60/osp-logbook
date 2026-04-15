"""Tests for backend/services/vehicle_service.py — VehicleService.delete_vehicle()."""

from unittest.mock import patch, MagicMock


class TestVehicleServiceDelete:
    """Test the VehicleService.delete_vehicle() static method."""

    @patch('backend.services.vehicle_service.AuditService')
    @patch('backend.services.vehicle_service.invalidate_prefix')
    @patch('backend.services.vehicle_service.get_cursor')
    @patch('backend.services.vehicle_service.get_db')
    def test_delete_success(self, mock_get_db, mock_get_cursor, mock_invalidate, mock_audit, app):
        """Successful delete commits, invalidates cache, and logs audit."""
        from backend.services.vehicle_service import VehicleService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        with app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            VehicleService.delete_vehicle(42, _user_id=1)

        mock_cur.execute.assert_called_once()
        assert 'DELETE FROM vehicles' in mock_cur.execute.call_args[0][0]
        mock_conn.commit.assert_called_once()
        mock_invalidate.assert_called_once_with('vehicles:')
        mock_audit.log.assert_called_once()

    @patch('backend.services.vehicle_service.AuditService')
    @patch('backend.services.vehicle_service.invalidate_prefix')
    @patch('backend.services.vehicle_service.get_cursor')
    @patch('backend.services.vehicle_service.get_db')
    def test_delete_db_error_rolls_back_and_raises(self, mock_get_db, mock_get_cursor, mock_invalidate, mock_audit, app):
        """DB error during delete rolls back and re-raises."""
        from backend.services.vehicle_service import VehicleService
        import pytest

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = Exception('FK violation')

        with app.test_request_context():
            with pytest.raises(Exception, match='FK violation'):
                VehicleService.delete_vehicle(42)

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()
        # Audit and cache invalidation should NOT be called on error
        mock_invalidate.assert_not_called()
        mock_audit.log.assert_not_called()
