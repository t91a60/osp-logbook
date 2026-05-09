"""Tests for backend/routes/equipment.py route behavior."""

from unittest.mock import MagicMock, patch


def _make_cursor(fetchall_result=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall_result if fetchall_result is not None else []
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    return cursor


class TestEquipmentListRoutes:
    @patch('backend.routes.equipment.render_template')
    @patch('backend.routes.equipment.get_vehicles_cached')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_list_returns_200(
        self,
        mock_get_db,
        mock_get_cursor,
        mock_get_vehicles,
        mock_render_template,
        authenticated_client,
    ):
        mock_get_db.return_value = MagicMock()
        mock_get_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_cursor = _make_cursor([{'id': 1, 'name': 'Torba R1', 'vname': 'GBA'}])
        mock_get_cursor.return_value = mock_cursor
        mock_render_template.return_value = 'equipment-page'

        response = authenticated_client.get('/sprzet')

        assert response.status_code == 200
        assert response.data == b'equipment-page'
        assert mock_render_template.call_args.args[0] == 'equipment.html'
        assert mock_render_template.call_args.kwargs['selected_vehicle'] == ''
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('backend.routes.equipment.render_template')
    @patch('backend.routes.equipment.get_vehicles_cached')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_list_filters_by_vehicle_id(
        self,
        mock_get_db,
        mock_get_cursor,
        mock_get_vehicles,
        mock_render_template,
        authenticated_client,
    ):
        mock_get_db.return_value = MagicMock()
        mock_get_vehicles.return_value = [{'id': 7, 'name': 'GCBA'}]
        filtered_items = [{'id': 2, 'name': 'Defibrylator AED', 'vehicle_id': 7, 'vname': 'GCBA'}]
        mock_cursor = _make_cursor(filtered_items)
        mock_get_cursor.return_value = mock_cursor
        mock_render_template.return_value = 'filtered-equipment-page'

        response = authenticated_client.get('/sprzet?vehicle_id=7')

        assert response.status_code == 200
        query, params = mock_cursor.execute.call_args.args
        assert 'WHERE e.vehicle_id = %s' in query
        assert params == ['7']
        assert mock_render_template.call_args.kwargs['items'] == filtered_items
        assert mock_render_template.call_args.kwargs['selected_vehicle'] == '7'


class TestEquipmentMutationRoutes:
    def test_equipment_add_requires_admin(self, authenticated_client):
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post(
            '/sprzet/dodaj',
            data={'_csrf_token': csrf, 'vehicle_id': '1', 'name': 'Torba R1'},
        )

        assert response.status_code == 403

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_add_redirects_on_success(self, mock_get_db, mock_get_cursor, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cursor = _make_cursor()
        mock_get_cursor.return_value = mock_cursor

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post(
            '/sprzet/dodaj',
            data={
                '_csrf_token': csrf,
                'vehicle_id': '3',
                'name': 'Defibrylator AED',
                'category': 'Ratownictwo medyczne',
                'quantity': '2',
                'unit': 'szt',
                'notes': 'Nowy sprzęt',
            },
        )

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/sprzet?vehicle_id=3')
        mock_cursor.execute.assert_called_once_with(
            'INSERT INTO equipment (vehicle_id, name, quantity, unit, category, notes) VALUES (%s,%s,%s,%s,%s,%s)',
            ('3', 'Defibrylator AED', 2, 'szt', 'Ratownictwo medyczne', 'Nowy sprzęt'),
        )
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_audit.log.assert_called_once_with('Dodanie', 'Sprzęt', 'Pojazd ID: 3, Nazwa: Defibrylator AED')

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_delete_redirects_on_success(self, mock_get_db, mock_get_cursor, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cursor = _make_cursor()
        mock_cursor.fetchone.return_value = {'vehicle_id': 5, 'name': 'Torba medyczna'}
        mock_get_cursor.return_value = mock_cursor

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/sprzet/9/usun', data={'_csrf_token': csrf})

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/sprzet?vehicle_id=5')
        assert mock_cursor.execute.call_args_list[0].args == (
            'SELECT vehicle_id, name FROM equipment WHERE id = %s',
            (9,),
        )
        assert mock_cursor.execute.call_args_list[1].args == ('DELETE FROM equipment WHERE id = %s', (9,))
        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once_with('Usunięcie', 'Sprzęt', 'ID: 9, Nazwa: Torba medyczna')
