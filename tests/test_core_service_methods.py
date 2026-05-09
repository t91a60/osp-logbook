"""Tests for backend/services/core_service.py — VehicleService and TripService methods."""

from unittest.mock import patch, MagicMock
import pytest


class TestGetLastKm:
    """Test VehicleService.get_last_km()."""

    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_returns_km_and_date(self, mock_get_db, mock_get_cursor, app):
        from backend.services.core_service import VehicleService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'km': 15000, 'dt': '2024-06-01'}

        with app.test_request_context():
            km, dt = VehicleService.get_last_km(1)

        assert km == 15000
        assert dt == '2024-06-01'
        mock_cur.close.assert_called_once()

    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_returns_none_none_when_no_data(self, mock_get_db, mock_get_cursor, app):
        from backend.services.core_service import VehicleService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with app.test_request_context():
            km, dt = VehicleService.get_last_km(999)

        assert km is None
        assert dt is None

    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_returns_none_when_km_is_null(self, mock_get_db, mock_get_cursor, app):
        from backend.services.core_service import VehicleService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'km': None, 'dt': '2024-01-01'}

        with app.test_request_context():
            km, dt = VehicleService.get_last_km(1)

        assert km is None
        assert dt is None


class TestGetRecentDrivers:
    """Test VehicleService.get_recent_drivers()."""

    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_returns_driver_list(self, mock_get_db, mock_get_cursor, app):
        from backend.services.core_service import VehicleService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {'driver': 'Anna'},
            {'driver': 'Jan'},
            {'driver': 'Marek'},
        ]

        with app.test_request_context():
            drivers = VehicleService.get_recent_drivers(days=90)

        assert drivers == ['Anna', 'Jan', 'Marek']
        mock_cur.close.assert_called_once()

    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_empty_when_no_drivers(self, mock_get_db, mock_get_cursor, app):
        from backend.services.core_service import VehicleService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with app.test_request_context():
            drivers = VehicleService.get_recent_drivers(days=30)

        assert drivers == []


class TestTripServiceAddFuel:
    """Test TripService.add_fuel()."""

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_add_fuel_success(self, mock_get_db, mock_get_cursor, mock_audit, app):
        from backend.services.core_service import TripService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        with app.test_request_context():
            TripService.add_fuel(
                vehicle_id='1', date_val='2024-01-01', driver='Jan',
                odometer='15000', liters='50.5', cost='320.00',
                notes='test', added_by='admin',
            )

        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_add_fuel_with_none_values(self, mock_get_db, mock_get_cursor, mock_audit, app):
        from backend.services.core_service import TripService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        with app.test_request_context():
            TripService.add_fuel(
                vehicle_id=None, date_val='2024-01-01', driver='Jan',
                odometer=None, liters=None, cost=None,
                notes='', added_by='admin',
            )

        mock_conn.commit.assert_called_once()

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_add_fuel_db_error_rolls_back(self, mock_get_db, mock_get_cursor, mock_audit, app):
        from backend.services.core_service import TripService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = Exception('DB error')

        with app.test_request_context():
            with pytest.raises(Exception, match='DB error'):
                TripService.add_fuel(
                    vehicle_id='1', date_val='2024-01-01', driver='Jan',
                    odometer='15000', liters='50', cost='300',
                    notes='', added_by='admin',
                )

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


class TestTripServiceAddMaintenance:
    """Test TripService.add_maintenance()."""

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_add_maintenance_success(self, mock_get_db, mock_get_cursor, mock_audit, app):
        from backend.services.core_service import TripService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        with app.test_request_context():
            TripService.add_maintenance(
                vehicle_id='1', date_val='2024-01-01', odometer='50000',
                description='Wymiana oleju', cost='250.00', notes='',
                added_by='admin', status='pending', priority='high',
                due_date='2024-04-01',
            )

        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.get_cursor')
    @patch('backend.services.core_service.get_db')
    def test_add_maintenance_db_error_rolls_back(self, mock_get_db, mock_get_cursor, mock_audit, app):
        from backend.services.core_service import TripService

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = Exception('DB error')

        with app.test_request_context():
            with pytest.raises(Exception, match='DB error'):
                TripService.add_maintenance(
                    vehicle_id='1', date_val='2024-01-01', odometer='50000',
                    description='Wymiana oleju', cost='250', notes='',
                    added_by='admin', status='pending', priority='medium',
                    due_date=None,
                )

        mock_conn.rollback.assert_called_once()


class TestTripServiceAddTrip:
    """Test TripService.add_trip() with equipment usage."""

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.TripRepository')
    def test_add_trip_with_equipment(self, mock_trip_repository, mock_audit, app):
        from backend.services.core_service import TripService

        equipment = [
            {'equipment_id': 1, 'quantity_used': 2, 'minutes_used': 30, 'notes': 'test'},
            {'equipment_id': 2, 'quantity_used': 1, 'minutes_used': 15},
        ]

        with app.test_request_context():
            TripService.add_trip(
                vehicle_id='1', date_val='2024-01-01', driver='Jan',
                odo_start='1000', odo_end='1050', purpose='Ćwiczenia',
                notes='', added_by='admin', equipment_used=equipment,
            )

        mock_trip_repository.add.assert_called_once()
        call_kwargs = mock_trip_repository.add.call_args.kwargs
        assert call_kwargs['equipment_used'] == equipment
        mock_audit.log.assert_called_once()

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.TripRepository')
    def test_add_trip_without_equipment(self, mock_trip_repository, mock_audit, app):
        from backend.services.core_service import TripService

        with app.test_request_context():
            TripService.add_trip(
                vehicle_id='1', date_val='2024-01-01', driver='Jan',
                odo_start=None, odo_end=None, purpose='Test',
                notes='', added_by='admin',
            )

        mock_trip_repository.add.assert_called_once()
        call_kwargs = mock_trip_repository.add.call_args.kwargs
        assert call_kwargs['equipment_used'] is None

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.TripRepository')
    def test_add_trip_with_empty_equipment_list(self, mock_trip_repository, mock_audit, app):
        from backend.services.core_service import TripService

        with app.test_request_context():
            TripService.add_trip(
                vehicle_id='1', date_val='2024-01-01', driver='Jan',
                odo_start='100', odo_end='200', purpose='Test',
                notes='', added_by='admin', equipment_used=[],
            )

        mock_trip_repository.add.assert_called_once()
        call_kwargs = mock_trip_repository.add.call_args.kwargs
        assert call_kwargs['equipment_used'] == []

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.TripRepository')
    def test_add_trip_delegates_equipment_payload(self, mock_trip_repository, mock_audit, app):
        """Service delegates raw equipment payload to repository layer."""
        from backend.services.core_service import TripService

        equipment = [
            {'equipment_id': None, 'quantity_used': 1, 'minutes_used': 10},
            {'equipment_id': '', 'quantity_used': 1, 'minutes_used': 10},
        ]

        with app.test_request_context():
            TripService.add_trip(
                vehicle_id='1', date_val='2024-01-01', driver='Jan',
                odo_start='100', odo_end='200', purpose='Test',
                notes='', added_by='admin', equipment_used=equipment,
            )

        call_kwargs = mock_trip_repository.add.call_args.kwargs
        assert call_kwargs['equipment_used'] == equipment
