from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.repositories.fuel import FuelRepository
from backend.domain.exceptions import ForbiddenError, NotFoundError


class TestFuelRepositoryAdd:
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_add_success(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        repo.add(
            vehicle_id='1',
            date_val='2024-01-01',
            driver='Jan',
            odometer='15000',
            liters='50.5',
            cost='320.00',
            notes='test',
            added_by='admin',
        )

        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_add_with_none_values(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        repo.add(
            vehicle_id=None,
            date_val='2024-01-01',
            driver='Jan',
            odometer=None,
            liters=None,
            cost=None,
            notes='',
            added_by='admin',
        )

        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_add_rolls_back_on_error(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError, match='db error'):
            repo.add(
                vehicle_id='1',
                date_val='2024-01-01',
                driver='Jan',
                odometer='15000',
                liters='50',
                cost='300',
                notes='',
                added_by='admin',
            )

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


class TestFuelRepositoryGetPage:
    @patch('backend.infrastructure.repositories.fuel.paginate')
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_page_returns_paginated_results(self, mock_get_db, mock_get_cursor, mock_paginate):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.return_value = ([{'id': 1}], 1, 1, 1)

        entries, total, total_pages, page = repo.get_page(vehicle_id='1', page=1)

        assert entries == [{'id': 1}]
        assert total == 1
        assert total_pages == 1
        assert page == 1
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.paginate')
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_page_no_vehicle_filter(self, mock_get_db, mock_get_cursor, mock_paginate):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_get_cursor.return_value = MagicMock()
        mock_paginate.return_value = ([], 0, 1, 1)

        entries, total, total_pages, page = repo.get_page()

        assert entries == []
        assert total == 0

    @patch('backend.infrastructure.repositories.fuel.paginate')
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_page_closes_cursor_on_error(self, mock_get_db, mock_get_cursor, mock_paginate):
        repo = FuelRepository()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError):
            repo.get_page()

        mock_cur.close.assert_called_once()


class TestFuelRepositoryGetById:
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_by_id_returns_row(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 42, 'liters': 50.0, 'vname': 'GBA'}

        result = repo.get_by_id(42)

        assert result == {'id': 42, 'liters': 50.0, 'vname': 'GBA'}
        mock_cur.execute.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_by_id_returns_none_when_missing(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        result = repo.get_by_id(999)

        assert result is None
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_by_id_closes_cursor_on_error(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.execute.side_effect = RuntimeError('boom')

        with pytest.raises(RuntimeError):
            repo.get_by_id(1)

        mock_cur.close.assert_called_once()


class TestFuelRepositoryUpdate:
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_update_success(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.rowcount = 1

        repo.update(
            entry_id=1,
            vehicle_id='2',
            date_val='2024-06-01',
            driver='Nowak',
            odometer='20000',
            liters='45.0',
            cost='280.00',
            notes='zaktualizowany',
        )

        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_update_raises_not_found_when_rowcount_zero(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.rowcount = 0

        with pytest.raises(NotFoundError):
            repo.update(
                entry_id=999,
                vehicle_id='1',
                date_val='2024-01-01',
                driver='X',
                odometer=None,
                liters='10',
                cost=None,
                notes='',
            )

        mock_conn.rollback.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_update_rolls_back_on_db_error(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError):
            repo.update(
                entry_id=1, vehicle_id='1', date_val='2024-01-01',
                driver='X', odometer=None, liters='10', cost=None, notes='',
            )

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


class TestFuelRepositoryDelete:
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_delete_success_owner(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}

        repo.delete(1, requester='jan')

        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_delete_success_admin(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}

        repo.delete(1, requester='admin', is_admin=True)

        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_delete_raises_not_found(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with pytest.raises(NotFoundError):
            repo.delete(999, requester='jan')

        mock_conn.rollback.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_delete_raises_forbidden_for_non_owner(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}

        with pytest.raises(ForbiddenError):
            repo.delete(1, requester='inny_user')

        mock_conn.rollback.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_delete_rolls_back_on_db_error(self, mock_get_db, mock_get_cursor):
        repo = FuelRepository()
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan', 'vehicle_id': 2}
        mock_cur.execute.side_effect = [None, RuntimeError('db error')]

        with pytest.raises(RuntimeError):
            repo.delete(1, requester='jan')

        mock_conn.rollback.assert_called_once()
        mock_cur.close.assert_called_once()
