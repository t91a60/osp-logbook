"""
Unit tests for AddFuelUseCase, EditFuelUseCase, DeleteFuelUseCase
in backend/application/fuel.py.

All tests use injected mock repositories — no Flask test client, no DB.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.application.fuel import (
    AddFuelCommand,
    AddFuelUseCase,
    DeleteFuelCommand,
    DeleteFuelUseCase,
    EditFuelCommand,
    EditFuelUseCase,
)
from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError


def _valid_add_cmd(**overrides):
    defaults = dict(
        vehicle_id='1',
        date_val='2026-05-12',
        driver='Jan Kowalski',
        odometer='37500',
        liters='40.5',
        cost='220.00',
        notes='',
        added_by='jan',
    )
    defaults.update(overrides)
    return AddFuelCommand(**defaults)


def _valid_edit_cmd(**overrides):
    defaults = dict(
        entry_id=1,
        vehicle_id='1',
        date_val='2026-05-12',
        driver='Jan Kowalski',
        odometer='37500',
        liters='40.5',
        cost='220.00',
        notes='',
        requester='jan',
        is_admin=False,
    )
    defaults.update(overrides)
    return EditFuelCommand(**defaults)


class TestAddFuelUseCase:
    def test_valid_fuel_entry_succeeds(self, mock_fuel_repo, mock_vehicle_repo):
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.fuel.AuditService'):
            uc.execute_instance(_valid_add_cmd())
        mock_fuel_repo.add.assert_called_once()

    def test_missing_driver_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(driver=''))

    def test_invalid_date_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(date_val='not-a-date'))

    def test_missing_liters_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(liters=None))

    def test_non_numeric_liters_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(liters='abc'))

    def test_negative_liters_accepted_by_use_case(self, mock_fuel_repo, mock_vehicle_repo):
        """AddFuelUseCase uses _to_float_field which only rejects non-numeric strings, not
        negative values. Positive-value enforcement is handled at the route/form layer, not
        in the use case itself. This test documents the current (permissive) behavior."""
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.fuel.AuditService'):
            uc.execute_instance(_valid_add_cmd(liters='-5'))
        mock_fuel_repo.add.assert_called_once()

    def test_zero_liters_accepted_by_use_case(self, mock_fuel_repo, mock_vehicle_repo):
        """AddFuelUseCase uses _to_float_field which only rejects non-numeric strings; it
        does not enforce a minimum value. Zero liters is therefore accepted at the use-case
        layer, with validation of minimum meaningful quantities left to the form/route layer.
        This test documents the current (permissive) behavior."""
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.fuel.AuditService'):
            uc.execute_instance(_valid_add_cmd(liters='0'))
        mock_fuel_repo.add.assert_called_once()

    def test_non_numeric_cost_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(cost='bad'))

    def test_invalid_vehicle_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        mock_vehicle_repo.get_active.return_value = None
        uc = AddFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd())


class TestEditFuelUseCase:
    def test_edit_fuel_updates_repo(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = {
            'id': 1, 'vehicle_id': 1, 'date': '2026-05-01',
            'driver': 'Jan', 'liters': 40.0, 'added_by': 'jan',
        }
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001'}
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with patch('backend.application.fuel.AuditService'):
            uc.execute_instance(_valid_edit_cmd())
        mock_fuel_repo.update.assert_called_once()

    def test_edit_nonexistent_fuel_raises_not_found(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = None
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(NotFoundError):
            uc.execute_instance(_valid_edit_cmd())

    def test_edit_by_non_owner_non_admin_raises_forbidden(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = {
            'id': 1, 'vehicle_id': 1, 'date': '2026-05-01',
            'driver': 'Jan', 'liters': 40.0, 'added_by': 'jan',
        }
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ForbiddenError):
            uc.execute_instance(_valid_edit_cmd(requester='other', is_admin=False))


class TestDeleteFuelUseCase:
    def test_delete_own_entry_succeeds(self, mock_fuel_repo):
        uc = DeleteFuelUseCase(fuel_repo=mock_fuel_repo)
        with patch('backend.application.fuel.AuditService'):
            uc.execute_instance(DeleteFuelCommand(entry_id=1, requester='jan', is_admin=False))
        mock_fuel_repo.delete.assert_called_once()

    def test_delete_others_entry_as_non_admin_raises_forbidden(self, mock_fuel_repo):
        mock_fuel_repo.delete.side_effect = ForbiddenError('Brak uprawnień')
        uc = DeleteFuelUseCase(fuel_repo=mock_fuel_repo)
        with pytest.raises(ForbiddenError):
            uc.execute_instance(DeleteFuelCommand(entry_id=1, requester='other', is_admin=False))

    def test_delete_others_entry_as_admin_succeeds(self, mock_fuel_repo):
        uc = DeleteFuelUseCase(fuel_repo=mock_fuel_repo)
        with patch('backend.application.fuel.AuditService'):
            uc.execute_instance(DeleteFuelCommand(entry_id=1, requester='other', is_admin=True))
        mock_fuel_repo.delete.assert_called_once_with(1, requester='other', is_admin=True)


class TestEditFuelUseCaseValidation:
    def _existing_entry(self):
        return {'id': 1, 'vehicle_id': 1, 'date': '2026-05-01',
                'driver': 'Jan', 'liters': 40.0, 'added_by': 'jan'}

    def test_edit_invalid_date_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = self._existing_entry()
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd(date_val='not-a-date'))

    def test_edit_missing_liters_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = self._existing_entry()
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd(liters=None))

    def test_edit_non_numeric_liters_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = self._existing_entry()
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd(liters='xyz'))

    def test_edit_non_numeric_cost_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = self._existing_entry()
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd(cost='bad'))

    def test_edit_invalid_vehicle_raises_validation_error(self, mock_fuel_repo, mock_vehicle_repo):
        mock_fuel_repo.get_by_id.return_value = self._existing_entry()
        mock_vehicle_repo.get_active.return_value = None
        uc = EditFuelUseCase(fuel_repo=mock_fuel_repo, vehicle_repo=mock_vehicle_repo)
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd())


class TestGetFuelUseCase:
    def test_get_fuel_returns_paginated_results(self, mock_fuel_repo):
        from backend.application.fuel import GetFuelQuery, GetFuelUseCase
        mock_fuel_repo.get_page.return_value = ([{'id': 1}], 1, 1, 1)
        uc = GetFuelUseCase(fuel_repo=mock_fuel_repo)
        entries, total, pages, page = uc.execute_instance(GetFuelQuery())
        assert entries == [{'id': 1}]
        assert total == 1

    def test_get_fuel_passes_filters_to_repo(self, mock_fuel_repo):
        from backend.application.fuel import GetFuelQuery, GetFuelUseCase
        mock_fuel_repo.get_page.return_value = ([], 0, 1, 1)
        uc = GetFuelUseCase(fuel_repo=mock_fuel_repo)
        uc.execute_instance(GetFuelQuery(vehicle_id='1', page=2))
        mock_fuel_repo.get_page.assert_called_once_with(
            vehicle_id='1', okres='', od='', do_='', page=2
        )


class TestGetFuelByIdUseCase:
    def test_get_by_id_returns_entry(self, mock_fuel_repo):
        from backend.application.fuel import GetFuelByIdUseCase
        mock_fuel_repo.get_by_id.return_value = {'id': 1, 'liters': 40.0}
        uc = GetFuelByIdUseCase(fuel_repo=mock_fuel_repo)
        result = uc.execute_instance(1)
        assert result['id'] == 1

    def test_get_by_id_returns_none_when_not_found(self, mock_fuel_repo):
        from backend.application.fuel import GetFuelByIdUseCase
        mock_fuel_repo.get_by_id.return_value = None
        uc = GetFuelByIdUseCase(fuel_repo=mock_fuel_repo)
        result = uc.execute_instance(999)
        assert result is None
