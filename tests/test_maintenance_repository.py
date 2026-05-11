from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.repositories.maintenance import MaintenanceRepository
from backend.domain.exceptions import ForbiddenError, NotFoundError


class TestMaintenanceRepositoryAdd:
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_add_success(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        MaintenanceRepository.add(
            vehicle_id='1',
            date_val='2024-01-01',
            odometer='50000',
            description='Wymiana oleju',
            cost='250.00',
            notes='test',
            added_by='admin',
            status='pending',
            priority='high',
            due_date='2024-04-01',
        )

        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_add_with_none_optional_fields(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        MaintenanceRepository.add(
            vehicle_id=None,
            date_val='2024-01-01',
            odometer=None,
            description='Test',
            cost=None,
            notes='',
            added_by='admin',
            status='pending',
            priority='medium',
            due_date=None,
        )

        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_add_rolls_back_on_error(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError, match='db error'):
            MaintenanceRepository.add(
                vehicle_id='1',
                date_val='2024-01-01',
                odometer='50000',
                description='Test',
                cost='100',
                notes='',
                added_by='admin',
                status='pending',
                priority='medium',
                due_date=None,
            )

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


class TestMaintenanceRepositoryGetPage:
    @patch('backend.infrastructure.repositories.maintenance.paginate')
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_page_returns_results(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.return_value = ([{'id': 1, 'effective_status': 'pending'}], 1, 1, 1)

        entries, total, total_pages, page = MaintenanceRepository.get_page(vehicle_id='1')

        assert entries == [{'id': 1, 'effective_status': 'pending'}]
        assert total == 1
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.paginate')
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_page_status_filter_pending(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_get_db.return_value = MagicMock()
        mock_get_cursor.return_value = MagicMock()
        mock_paginate.return_value = ([], 0, 1, 1)

        entries, total, _, _ = MaintenanceRepository.get_page(status_filter='pending')

        assert entries == []
        # verify paginate was called with SQL containing the pending filter
        call_args = mock_paginate.call_args
        base_sql = call_args[0][4]
        assert 'pending' in base_sql

    @patch('backend.infrastructure.repositories.maintenance.paginate')
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_page_status_filter_completed(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_get_db.return_value = MagicMock()
        mock_get_cursor.return_value = MagicMock()
        mock_paginate.return_value = ([], 0, 1, 1)

        MaintenanceRepository.get_page(status_filter='completed')

        call_args = mock_paginate.call_args
        base_sql = call_args[0][4]
        assert 'completed' in base_sql

    @patch('backend.infrastructure.repositories.maintenance.paginate')
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_page_status_filter_overdue(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_get_db.return_value = MagicMock()
        mock_get_cursor.return_value = MagicMock()
        mock_paginate.return_value = ([], 0, 1, 1)

        MaintenanceRepository.get_page(status_filter='overdue')

        call_args = mock_paginate.call_args
        base_sql = call_args[0][4]
        assert 'overdue' in base_sql or 'due_date' in base_sql

    @patch('backend.infrastructure.repositories.maintenance.paginate')
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_page_closes_cursor_on_error(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError):
            MaintenanceRepository.get_page()

        mock_cur.close.assert_called_once()


class TestMaintenanceRepositoryComplete:
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_complete_returns_row(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'testuser'}

        row = MaintenanceRepository.complete(1)

        assert row == {'id': 1, 'added_by': 'testuser'}
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_complete_returns_none_when_not_found(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        row = MaintenanceRepository.complete(999)

        assert row is None
        mock_conn.commit.assert_not_called()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_complete_rolls_back_on_error(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'testuser'}
        mock_cur.execute.side_effect = [None, RuntimeError('db error')]

        with pytest.raises(RuntimeError):
            MaintenanceRepository.complete(1)

        mock_conn.rollback.assert_called_once()


class TestMaintenanceRepositoryCreateNext:
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_create_next_returns_original_row(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'vehicle_id': 1,
            'odometer': 50000,
            'description': 'Wymiana oleju',
            'notes': '',
            'priority': 'high',
            'due_date': '2024-03-01',
            'added_by': 'testuser',
        }

        row = MaintenanceRepository.create_next(1)

        assert row['description'] == 'Wymiana oleju'
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_create_next_returns_none_when_not_found(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        row = MaintenanceRepository.create_next(999)

        assert row is None
        mock_conn.commit.assert_not_called()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_create_next_with_no_due_date_uses_today_plus_90(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'vehicle_id': 1,
            'odometer': 10000,
            'description': 'Test',
            'notes': '',
            'priority': 'medium',
            'due_date': None,
            'added_by': 'admin',
        }

        row = MaintenanceRepository.create_next(1)

        assert row is not None
        mock_conn.commit.assert_called_once()
        insert_call_args = mock_cur.execute.call_args_list[-1]
        # The inserted due_date should be today + 90 days
        expected_due = (date.today().toordinal() + 90)
        inserted_due = date.fromisoformat(insert_call_args[0][1][-1]).toordinal()
        assert inserted_due == expected_due

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_create_next_with_invalid_due_date_falls_back(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'vehicle_id': 1,
            'odometer': None,
            'description': 'Test',
            'notes': '',
            'priority': 'medium',
            'due_date': 'not-a-date',
            'added_by': 'admin',
        }

        row = MaintenanceRepository.create_next(1)

        assert row is not None
        mock_conn.commit.assert_called_once()


class TestMaintenanceRepositoryGetById:
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_by_id_returns_row(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 5, 'description': 'Serwis', 'effective_status': 'pending', 'vname': 'GBA'
        }

        result = MaintenanceRepository.get_by_id(5)

        assert result['id'] == 5
        assert result['effective_status'] == 'pending'
        mock_cur.execute.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_by_id_returns_none_when_missing(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        result = MaintenanceRepository.get_by_id(999)

        assert result is None
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_get_by_id_closes_cursor_on_error(self, mock_get_db, mock_get_cursor):
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.execute.side_effect = RuntimeError('boom')

        with pytest.raises(RuntimeError):
            MaintenanceRepository.get_by_id(1)

        mock_cur.close.assert_called_once()


class TestMaintenanceRepositoryUpdate:
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_update_success(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.rowcount = 1

        MaintenanceRepository.update(
            entry_id=1,
            vehicle_id='2',
            date_val='2024-06-01',
            odometer='55000',
            description='Wymiana tarcz',
            cost='500.00',
            notes='zaktualizowany',
            status='completed',
            priority='high',
            due_date=None,
        )

        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_update_raises_not_found_when_rowcount_zero(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.rowcount = 0

        with pytest.raises(NotFoundError):
            MaintenanceRepository.update(
                entry_id=999,
                vehicle_id='1',
                date_val='2024-01-01',
                odometer=None,
                description='X',
                cost=None,
                notes='',
                status='pending',
                priority='medium',
                due_date=None,
            )

        mock_conn.rollback.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_update_rolls_back_on_db_error(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError):
            MaintenanceRepository.update(
                entry_id=1, vehicle_id='1', date_val='2024-01-01', odometer=None,
                description='X', cost=None, notes='', status='pending',
                priority='medium', due_date=None,
            )

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


class TestMaintenanceRepositoryDelete:
    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_delete_success_owner(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}

        MaintenanceRepository.delete(1, requester='jan')

        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_delete_success_admin(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}

        MaintenanceRepository.delete(1, requester='admin', is_admin=True)

        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_delete_raises_not_found(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with pytest.raises(NotFoundError):
            MaintenanceRepository.delete(999, requester='jan')

        mock_conn.rollback.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_delete_raises_forbidden_for_non_owner(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}

        with pytest.raises(ForbiddenError):
            MaintenanceRepository.delete(1, requester='inny_user')

        mock_conn.rollback.assert_called_once()

    @patch('backend.infrastructure.repositories.maintenance.get_cursor')
    @patch('backend.infrastructure.repositories.maintenance.get_db')
    def test_delete_rolls_back_on_db_error(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}
        mock_cur.execute.side_effect = [None, RuntimeError('db error')]

        with pytest.raises(RuntimeError):
            MaintenanceRepository.delete(1, requester='jan')

        mock_conn.rollback.assert_called_once()
        mock_cur.close.assert_called_once()
