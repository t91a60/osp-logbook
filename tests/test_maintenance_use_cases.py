"""
Unit tests for maintenance use cases in backend/application/maintenance.py.

Covers: AddMaintenanceUseCase, EditMaintenanceUseCase, DeleteMaintenanceUseCase,
CompleteMaintenanceUseCase, CreateNextMaintenanceUseCase.

All tests use injected mock repositories — no Flask test client, no DB.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.application.maintenance import (
    AddMaintenanceCommand,
    AddMaintenanceUseCase,
    CompleteMaintenanceCommand,
    CompleteMaintenanceUseCase,
    CreateNextMaintenanceCommand,
    CreateNextMaintenanceUseCase,
    DeleteMaintenanceCommand,
    DeleteMaintenanceUseCase,
    EditMaintenanceCommand,
    EditMaintenanceUseCase,
)
from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError


def _valid_add_cmd(**overrides):
    defaults = dict(
        vehicle_id='1',
        date_val='2026-05-12',
        description='Wymiana oleju',
        odometer='37500',
        cost='250.00',
        notes='',
        added_by='jan',
        status='pending',
        priority='medium',
        due_date=None,
    )
    defaults.update(overrides)
    return AddMaintenanceCommand(**defaults)


def _valid_edit_cmd(**overrides):
    defaults = dict(
        entry_id=1,
        vehicle_id='1',
        date_val='2026-05-12',
        description='Wymiana oleju',
        odometer='37500',
        cost='250.00',
        notes='',
        requester='jan',
        status='pending',
        priority='medium',
        due_date=None,
        is_admin=False,
    )
    defaults.update(overrides)
    return EditMaintenanceCommand(**defaults)


class TestAddMaintenanceUseCase:
    def test_add_maintenance_valid(self, mock_maintenance_repo, mock_vehicle_repo):
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with patch('backend.application.maintenance.AuditService'):
            uc.execute_instance(_valid_add_cmd())
        mock_maintenance_repo.add.assert_called_once()

    def test_add_maintenance_missing_description_raises(self, mock_maintenance_repo, mock_vehicle_repo):
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(description=''))

    def test_add_maintenance_invalid_date_raises(self, mock_maintenance_repo, mock_vehicle_repo):
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(date_val='not-a-date'))

    def test_add_maintenance_invalid_odometer_raises(self, mock_maintenance_repo, mock_vehicle_repo):
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(odometer='bad'))

    def test_add_maintenance_non_numeric_cost_raises(self, mock_maintenance_repo, mock_vehicle_repo):
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd(cost='bad'))

    def test_add_maintenance_invalid_priority_uses_default(self, mock_maintenance_repo, mock_vehicle_repo):
        """Invalid priority falls back to 'medium' (no exception raised)."""
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with patch('backend.application.maintenance.AuditService'):
            uc.execute_instance(_valid_add_cmd(priority='invalid_priority'))
        # Should not raise; repo.add should have been called with priority='medium'
        mock_maintenance_repo.add.assert_called_once()
        call_kwargs = mock_maintenance_repo.add.call_args.kwargs
        assert call_kwargs['priority'] == 'medium'

    def test_add_maintenance_invalid_status_uses_default(self, mock_maintenance_repo, mock_vehicle_repo):
        """Invalid status falls back to 'pending' (no exception raised)."""
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with patch('backend.application.maintenance.AuditService'):
            uc.execute_instance(_valid_add_cmd(status='invalid_status'))
        mock_maintenance_repo.add.assert_called_once()
        call_kwargs = mock_maintenance_repo.add.call_args.kwargs
        assert call_kwargs['status'] == 'pending'

    def test_add_maintenance_invalid_vehicle_raises(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_vehicle_repo.get_active.return_value = None
        uc = AddMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_add_cmd())


class TestCompleteMaintenanceUseCase:
    def test_complete_maintenance_marks_completed(self, mock_maintenance_repo):
        mock_maintenance_repo.complete.return_value = {'id': 1, 'status': 'completed', 'added_by': 'jan'}
        uc = CompleteMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with patch('backend.application.maintenance.AuditService'):
            result = uc.execute_instance(
                CompleteMaintenanceCommand(entry_id=1, requester='jan', is_admin=False)
            )
        assert result['status'] == 'completed'

    def test_complete_nonexistent_raises_not_found(self, mock_maintenance_repo):
        mock_maintenance_repo.complete.return_value = None
        uc = CompleteMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with pytest.raises(NotFoundError):
            uc.execute_instance(
                CompleteMaintenanceCommand(entry_id=999, requester='jan', is_admin=False)
            )

    def test_complete_by_non_owner_raises_forbidden(self, mock_maintenance_repo):
        mock_maintenance_repo.complete.return_value = {'id': 1, 'status': 'completed', 'added_by': 'jan'}
        uc = CompleteMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with pytest.raises(ForbiddenError):
            uc.execute_instance(
                CompleteMaintenanceCommand(entry_id=1, requester='other', is_admin=False)
            )

    def test_complete_by_admin_succeeds_regardless_of_owner(self, mock_maintenance_repo):
        mock_maintenance_repo.complete.return_value = {'id': 1, 'status': 'completed', 'added_by': 'jan'}
        uc = CompleteMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with patch('backend.application.maintenance.AuditService'):
            result = uc.execute_instance(
                CompleteMaintenanceCommand(entry_id=1, requester='admin', is_admin=True)
            )
        assert result['status'] == 'completed'


class TestCreateNextMaintenanceUseCase:
    def test_create_next_duplicates_entry_with_new_date(self, mock_maintenance_repo):
        mock_maintenance_repo.create_next.return_value = {'id': 2, 'status': 'pending', 'added_by': 'jan'}
        uc = CreateNextMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with patch('backend.application.maintenance.AuditService'):
            result = uc.execute_instance(
                CreateNextMaintenanceCommand(entry_id=1, added_by='jan', requester='jan', is_admin=False)
            )
        assert result['id'] == 2
        assert result['status'] == 'pending'

    def test_create_next_nonexistent_raises_not_found(self, mock_maintenance_repo):
        mock_maintenance_repo.create_next.return_value = None
        uc = CreateNextMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with pytest.raises(NotFoundError):
            uc.execute_instance(
                CreateNextMaintenanceCommand(entry_id=999, added_by='jan', requester='jan', is_admin=False)
            )

    def test_create_next_by_non_owner_raises_forbidden(self, mock_maintenance_repo):
        mock_maintenance_repo.create_next.return_value = {'id': 2, 'status': 'pending', 'added_by': 'jan'}
        uc = CreateNextMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with pytest.raises(ForbiddenError):
            uc.execute_instance(
                CreateNextMaintenanceCommand(entry_id=1, added_by='jan', requester='other', is_admin=False)
            )


class TestDeleteMaintenanceUseCase:
    def test_delete_maintenance_as_non_owner_raises_forbidden(self, mock_maintenance_repo):
        mock_maintenance_repo.delete.side_effect = ForbiddenError('Brak uprawnień')
        uc = DeleteMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with pytest.raises(ForbiddenError):
            uc.execute_instance(
                DeleteMaintenanceCommand(entry_id=1, requester='other', is_admin=False)
            )

    def test_delete_maintenance_as_owner_succeeds(self, mock_maintenance_repo):
        uc = DeleteMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        with patch('backend.application.maintenance.AuditService'):
            uc.execute_instance(
                DeleteMaintenanceCommand(entry_id=1, requester='jan', is_admin=False)
            )
        mock_maintenance_repo.delete.assert_called_once()


class TestEditMaintenanceUseCase:
    def test_edit_maintenance_updates_correctly(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_maintenance_repo.get_by_id.return_value = {
            'id': 1, 'description': 'Stary opis', 'added_by': 'jan', 'status': 'pending',
        }
        mock_vehicle_repo.get_active.return_value = {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001'}
        uc = EditMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with patch('backend.application.maintenance.AuditService'):
            uc.execute_instance(_valid_edit_cmd())
        mock_maintenance_repo.update.assert_called_once()

    def test_edit_nonexistent_maintenance_raises_not_found(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_maintenance_repo.get_by_id.return_value = None
        uc = EditMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(NotFoundError):
            uc.execute_instance(_valid_edit_cmd())

    def test_edit_by_non_owner_raises_forbidden(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_maintenance_repo.get_by_id.return_value = {
            'id': 1, 'description': 'Opis', 'added_by': 'jan', 'status': 'pending',
        }
        uc = EditMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ForbiddenError):
            uc.execute_instance(_valid_edit_cmd(requester='other', is_admin=False))

    def test_edit_invalid_date_raises_validation_error(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_maintenance_repo.get_by_id.return_value = {
            'id': 1, 'description': 'Opis', 'added_by': 'jan', 'status': 'pending',
        }
        uc = EditMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd(date_val='not-a-date'))

    def test_edit_invalid_odometer_raises_validation_error(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_maintenance_repo.get_by_id.return_value = {
            'id': 1, 'description': 'Opis', 'added_by': 'jan', 'status': 'pending',
        }
        uc = EditMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd(odometer='bad'))

    def test_edit_invalid_vehicle_raises_validation_error(self, mock_maintenance_repo, mock_vehicle_repo):
        mock_maintenance_repo.get_by_id.return_value = {
            'id': 1, 'description': 'Opis', 'added_by': 'jan', 'status': 'pending',
        }
        mock_vehicle_repo.get_active.return_value = None
        uc = EditMaintenanceUseCase(
            maintenance_repo=mock_maintenance_repo, vehicle_repo=mock_vehicle_repo
        )
        with pytest.raises(ValidationError):
            uc.execute_instance(_valid_edit_cmd())


class TestGetMaintenanceUseCase:
    def test_get_maintenance_returns_paginated_results(self, mock_maintenance_repo):
        from backend.application.maintenance import GetMaintenanceQuery, GetMaintenanceUseCase
        mock_maintenance_repo.get_page.return_value = ([{'id': 1}], 1, 1, 1)
        uc = GetMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        entries, total, pages, page = uc.execute_instance(GetMaintenanceQuery())
        assert entries == [{'id': 1}]

    def test_get_maintenance_passes_filters(self, mock_maintenance_repo):
        from backend.application.maintenance import GetMaintenanceQuery, GetMaintenanceUseCase
        mock_maintenance_repo.get_page.return_value = ([], 0, 1, 1)
        uc = GetMaintenanceUseCase(maintenance_repo=mock_maintenance_repo)
        uc.execute_instance(GetMaintenanceQuery(vehicle_id='1', status_filter='pending'))
        mock_maintenance_repo.get_page.assert_called_once_with(
            vehicle_id='1', status_filter='pending', okres='', od='', do_='', page=1
        )


class TestGetMaintenanceByIdUseCase:
    def test_get_by_id_returns_entry(self, mock_maintenance_repo):
        from backend.application.maintenance import GetMaintenanceByIdUseCase
        mock_maintenance_repo.get_by_id.return_value = {'id': 1, 'description': 'Serwis'}
        uc = GetMaintenanceByIdUseCase(maintenance_repo=mock_maintenance_repo)
        result = uc.execute_instance(1)
        assert result['id'] == 1

    def test_get_by_id_returns_none_when_not_found(self, mock_maintenance_repo):
        from backend.application.maintenance import GetMaintenanceByIdUseCase
        mock_maintenance_repo.get_by_id.return_value = None
        uc = GetMaintenanceByIdUseCase(maintenance_repo=mock_maintenance_repo)
        assert uc.execute_instance(999) is None
