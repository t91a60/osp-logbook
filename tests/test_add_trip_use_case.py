"""
Unit tests for AddTripUseCase in backend/application/trips.py.

All tests use injected mock repositories — no Flask test client, no DB.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.application.trips import AddTripCommand, AddTripUseCase
from backend.domain.exceptions import ValidationError


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


def _make_use_case(trip_repo=None, vehicle_repo=None):
    if trip_repo is None:
        trip_repo = MagicMock()
        trip_repo.add.return_value = 42
    if vehicle_repo is None:
        vehicle_repo = MagicMock()
        vehicle_repo.get_active.return_value = {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001'}
    return AddTripUseCase(trip_repo=trip_repo, vehicle_repo=vehicle_repo)


class TestAddTripUseCaseValidation:
    def test_valid_trip_returns_trip_id(self, mock_trip_repo, mock_vehicle_repo):
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'Fiat'}
        mock_trip_repo.add.return_value = 42
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.trips.AuditService'), \
             patch('backend.application.trips.invalidate_prefix'):
            result = uc.execute_instance(_valid_cmd())
        assert result == 42

    def test_missing_driver_raises_validation_error(self, mock_trip_repo, mock_vehicle_repo):
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError, match='Kierowca'):
            uc.execute_instance(_valid_cmd(driver='   '))

    def test_missing_purpose_raises_validation_error(self, mock_trip_repo, mock_vehicle_repo):
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_cmd(purpose=''))

    def test_invalid_date_format_raises_validation_error(self, mock_trip_repo, mock_vehicle_repo):
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_cmd(date_val='not-a-date'))

    def test_odo_end_less_than_start_raises_validation_error(self, mock_trip_repo, mock_vehicle_repo):
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_cmd(odo_start='500', odo_end='100'))

    def test_negative_odometer_raises_validation_error(self, mock_trip_repo, mock_vehicle_repo):
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_cmd(odo_start='-50'))

    def test_inactive_vehicle_raises_validation_error(self, mock_trip_repo, mock_vehicle_repo):
        mock_vehicle_repo.get_active.return_value = None
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError, match='pojazd'):
            uc.execute_instance(_valid_cmd())

    def test_repo_add_not_called_on_validation_failure(self, mock_trip_repo, mock_vehicle_repo):
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_cmd(driver=''))
        mock_trip_repo.add.assert_not_called()


class TestAddTripUseCaseSideEffects:
    def test_audit_log_called_on_success(self, mock_trip_repo, mock_vehicle_repo):
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'GBA', 'plate': 'SBI 001'}
        mock_trip_repo.add.return_value = 1
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.trips.AuditService') as mock_audit, \
             patch('backend.application.trips.invalidate_prefix'):
            uc.execute_instance(_valid_cmd())
        mock_audit.log.assert_called_once()
        args = mock_audit.log.call_args.args
        assert args[0] == 'Dodanie'
        assert args[1] == 'Wyjazd'

    def test_cache_invalidated_on_success(self, mock_trip_repo, mock_vehicle_repo):
        mock_vehicle_repo.get_active.return_value = {'id': 5, 'name': 'GBA', 'plate': 'SBI 005'}
        mock_trip_repo.add.return_value = 10
        uc = AddTripUseCase(trip_repo=mock_trip_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.trips.AuditService'), \
             patch('backend.application.trips.invalidate_prefix') as mock_inv:
            uc.execute_instance(_valid_cmd(vehicle_id='5'))
        mock_inv.assert_called_once_with('report:5:')
