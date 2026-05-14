"""
Unit tests for backend/application/trips.py

AddTripUseCase:
  - Validates command fields before touching the DB.
  - Delegates to TripRepository.add and emits side effects.

GetTripsUseCase:
  - Thin delegation to TripRepository.get_page — verified via mock.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.application.trips import (
    AddTripCommand,
    AddTripUseCase,
    GetTripsQuery,
    GetTripsUseCase,
)
from backend.domain.exceptions import ValidationError


# ---------------------------------------------------------------------------
# AddTripUseCase
# ---------------------------------------------------------------------------

def _valid_cmd(**overrides) -> AddTripCommand:
    defaults = dict(
        vehicle_id='1',
        date_val='2026-05-12',
        driver='Jan Kowalski',
        odo_start='10000',
        odo_end='10120',
        purpose='Pożar lasu',
        notes='',
        added_by='admin',
    )
    defaults.update(overrides)
    return AddTripCommand(**defaults)


class TestAddTripUseCaseValidation:
    def test_missing_driver_raises_validation_error(self):
        trip_repo = MagicMock()
        vehicle_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)
        cmd = _valid_cmd(driver='')
        with pytest.raises(ValidationError, match='Kierowca'):
            uc.execute_instance(cmd)

    def test_missing_purpose_raises_validation_error(self):
        trip_repo = MagicMock()
        vehicle_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)
        cmd = _valid_cmd(purpose='')
        with pytest.raises(ValidationError, match='Cel wyjazdu'):
            uc.execute_instance(cmd)

    def test_bad_date_format_raises_validation_error(self):
        trip_repo = MagicMock()
        vehicle_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)
        cmd = _valid_cmd(date_val='12-05-2026')
        with pytest.raises(ValidationError):
            uc.execute_instance(cmd)

    def test_odometer_end_less_than_start_raises_validation_error(self):
        trip_repo = MagicMock()
        vehicle_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)
        cmd = _valid_cmd(odo_start='500', odo_end='400')
        with pytest.raises(ValidationError):
            uc.execute_instance(cmd)

    def test_negative_odo_raises_validation_error(self):
        trip_repo = MagicMock()
        vehicle_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)
        cmd = _valid_cmd(odo_start='-10', odo_end='100')
        with pytest.raises(ValidationError):
            uc.execute_instance(cmd)

    def test_invalid_vehicle_raises_validation_error(self):
        trip_repo = MagicMock()
        vehicle_repo = MagicMock()
        vehicle_repo.get_active.return_value = None
        uc = AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)
        cmd = _valid_cmd(vehicle_id='999')
        with pytest.raises(ValidationError, match='pojazd'):
            uc.execute_instance(cmd)


class TestAddTripUseCaseSuccess:
    @patch('backend.application.trips.invalidate_prefix')
    @patch('backend.application.trips.AuditService')
    def test_returns_trip_id(self, mock_audit, mock_inv):
        mock_vehicle_repo = MagicMock()
        mock_trip_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'GBA'}
        mock_trip_repo.add.return_value = 42

        cmd = _valid_cmd()
        trip_id = uc.execute_instance(cmd)

        assert trip_id == 42

    @patch('backend.application.trips.invalidate_prefix')
    @patch('backend.application.trips.AuditService')
    def test_calls_trip_repository_add(self, mock_audit, mock_inv):
        mock_vehicle_repo = MagicMock()
        mock_trip_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'GBA'}
        mock_trip_repo.add.return_value = 1

        uc.execute_instance(_valid_cmd())

        mock_trip_repo.add.assert_called_once()
        call_kwargs = mock_trip_repo.add.call_args.kwargs
        assert call_kwargs['driver'] == 'Jan Kowalski'
        assert call_kwargs['purpose'] == 'Pożar lasu'
        assert call_kwargs['odo_start'] == 10000
        assert call_kwargs['odo_end'] == 10120

    @patch('backend.application.trips.invalidate_prefix')
    @patch('backend.application.trips.AuditService')
    def test_emits_audit_log(self, mock_audit, mock_inv):
        mock_vehicle_repo = MagicMock()
        mock_trip_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'GBA'}
        mock_trip_repo.add.return_value = 1

        uc.execute_instance(_valid_cmd())

        mock_audit.log.assert_called_once()
        args = mock_audit.log.call_args.args
        assert args[0] == 'Dodanie'
        assert args[1] == 'Wyjazd'

    @patch('backend.application.trips.invalidate_prefix')
    @patch('backend.application.trips.AuditService')
    def test_none_odo_accepted(self, mock_audit, mock_inv):
        mock_vehicle_repo = MagicMock()
        mock_trip_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'GBA'}
        mock_trip_repo.add.return_value = 1

        cmd = _valid_cmd(odo_start=None, odo_end=None)
        trip_id = uc.execute_instance(cmd)

        assert trip_id == 1
        call_kwargs = mock_trip_repo.add.call_args.kwargs
        assert call_kwargs['odo_start'] is None
        assert call_kwargs['odo_end'] is None

    @patch('backend.application.trips.invalidate_prefix')
    @patch('backend.application.trips.AuditService')
    def test_cache_invalidation_called(self, mock_audit, mock_inv):
        mock_vehicle_repo = MagicMock()
        mock_trip_repo = MagicMock()
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        mock_vehicle_repo.get_active.return_value = {'id': 5, 'name': 'GBA'}
        mock_trip_repo.add.return_value = 10

        uc.execute_instance(_valid_cmd(vehicle_id='5'))

        mock_inv.assert_called_once_with('report:5:')


# ---------------------------------------------------------------------------
# GetTripsUseCase
# ---------------------------------------------------------------------------

class TestGetTripsUseCase:
    def test_delegates_to_repository(self):
        mock_repo = MagicMock()
        uc = GetTripsUseCase(trip_repo=mock_repo)
        mock_repo.get_page.return_value = ([{'id': 1}], 1, 1, 1)

        q = GetTripsQuery(vehicle_id='1', page=1)
        entries, total, total_pages, page = uc.execute_instance(q)

        assert entries == [{'id': 1}]
        assert total == 1
        mock_repo.get_page.assert_called_once_with(
            vehicle_id='1',
            okres='',
            od='',
            do_='',
            page=1,
        )

    def test_default_query_values(self):
        mock_repo = MagicMock()
        uc = GetTripsUseCase(trip_repo=mock_repo)
        mock_repo.get_page.return_value = ([], 0, 1, 1)

        uc.execute_instance(GetTripsQuery())

        mock_repo.get_page.assert_called_once_with(
            vehicle_id=None,
            okres='',
            od='',
            do_='',
            page=1,
        )
