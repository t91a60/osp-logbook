from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.repositories.fuel import FuelRepository


class TestFuelRepositoryAdd:
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_add_success(self, mock_get_db, mock_get_cursor):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        FuelRepository.add(
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
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        FuelRepository.add(
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
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError, match='db error'):
            FuelRepository.add(
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
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.return_value = ([{'id': 1}], 1, 1, 1)

        entries, total, total_pages, page = FuelRepository.get_page(vehicle_id='1', page=1)

        assert entries == [{'id': 1}]
        assert total == 1
        assert total_pages == 1
        assert page == 1
        mock_cur.close.assert_called_once()

    @patch('backend.infrastructure.repositories.fuel.paginate')
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_page_no_vehicle_filter(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_get_cursor.return_value = MagicMock()
        mock_paginate.return_value = ([], 0, 1, 1)

        entries, total, total_pages, page = FuelRepository.get_page()

        assert entries == []
        assert total == 0

    @patch('backend.infrastructure.repositories.fuel.paginate')
    @patch('backend.infrastructure.repositories.fuel.get_cursor')
    @patch('backend.infrastructure.repositories.fuel.get_db')
    def test_get_page_closes_cursor_on_error(self, mock_get_db, mock_get_cursor, mock_paginate):
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_paginate.side_effect = RuntimeError('db error')

        with pytest.raises(RuntimeError):
            FuelRepository.get_page()

        mock_cur.close.assert_called_once()
