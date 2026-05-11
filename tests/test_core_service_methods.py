"""Tests for backend/services/core_service.py — TripService orchestration."""

from unittest.mock import MagicMock, patch


class TestTripServiceAddTrip:
    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.TripRepository')
    def test_add_trip_delegates_to_repository_and_audit(self, mock_trip_repository, mock_audit, app):
        from backend.services.core_service import TripService

        with app.test_request_context():
            TripService.add_trip(
                vehicle_id='1',
                date_val='2024-01-01',
                driver='Jan',
                odo_start='1000',
                odo_end='1050',
                purpose='Ćwiczenia',
                notes='notatki',
                added_by='admin',
                time_start='08:00',
                time_end='09:00',
                equipment_used=[{'equipment_id': 1, 'quantity_used': 1, 'minutes_used': 15}],
            )

        mock_trip_repository.add.assert_called_once()
        assert mock_trip_repository.add.call_args.kwargs['purpose'] == 'Ćwiczenia'
        mock_audit.log.assert_called_once()

    @patch('backend.services.core_service.AuditService')
    @patch('backend.services.core_service.TripRepository')
    def test_add_trip_forwards_none_equipment(self, mock_trip_repository, mock_audit, app):
        from backend.services.core_service import TripService

        with app.test_request_context():
            TripService.add_trip(
                vehicle_id='1',
                date_val='2024-01-01',
                driver='Jan',
                odo_start=None,
                odo_end=None,
                purpose='Test',
                notes='',
                added_by='admin',
            )

        assert mock_trip_repository.add.call_args.kwargs['equipment_used'] is None
        mock_audit.log.assert_called_once()
