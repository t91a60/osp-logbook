from unittest.mock import MagicMock, patch

import pytest

from backend.domain.exceptions import ForbiddenError, NotFoundError
from backend.infrastructure.repositories.trips import TripRepository


class TestTripRepositoryAdd:
    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_add_with_equipment(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {'id': 42}

        trip_id = TripRepository.add(
            vehicle_id='1',
            date_val='2024-01-01',
            driver='Jan',
            odo_start='100',
            odo_end='150',
            purpose='Test',
            notes='',
            added_by='admin',
            equipment_used=[{'equipment_id': 2, 'quantity_used': 1, 'minutes_used': 20}],
        )

        assert trip_id == 42
        mock_cur.execute.assert_called()
        mock_cur.executemany.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_add_rolls_back_on_error(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError, match='db error'):
            TripRepository.add(
                vehicle_id='1',
                date_val='2024-01-01',
                driver='Jan',
                odo_start='100',
                odo_end='150',
                purpose='Test',
                notes='',
                added_by='admin',
            )

        mock_conn.rollback.assert_called_once()


class TestTripRepositoryQueries:
    @patch('backend.infrastructure.repositories.trips.paginate')
    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_get_page_uses_paginate(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.return_value = ([{'id': 1}], 1, 1, 1)

        entries, total, total_pages, page = TripRepository.get_page(vehicle_id='1', page=1)

        assert entries == [{'id': 1}]
        assert total == 1
        assert total_pages == 1
        assert page == 1
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.trips.get_active_vehicle')
    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_get_active_vehicle(self, mock_get_db, mock_get_cursor, mock_get_active_vehicle):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_get_active_vehicle.return_value = {'id': 1}

        vehicle = TripRepository.get_active_vehicle('1')

        assert vehicle == {'id': 1}
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_get_by_id_returns_row(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 7, 'vname': 'Auto 1'}

        row = TripRepository.get_by_id(7)

        assert row == {'id': 7, 'vname': 'Auto 1'}
        mock_cur.execute.assert_called_once()
        mock_cur.close.assert_called_once()


class TestTripRepositoryDelete:
    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_delete_not_found_raises(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with pytest.raises(NotFoundError):
            TripRepository.delete(1, requester='jan')

        mock_conn.rollback.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_delete_forbidden_raises(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'admin'}

        with pytest.raises(ForbiddenError):
            TripRepository.delete(1, requester='jan', is_admin=False)

        mock_conn.rollback.assert_called_once()
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.trips.get_cursor')
    @patch('backend.infrastructure.repositories.trips.get_db')
    def test_delete_success_for_owner(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'added_by': 'jan'}

        TripRepository.delete(1, requester='jan', is_admin=False)

        assert mock_cur.execute.call_count == 3
        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()
