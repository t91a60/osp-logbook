"""Extended tests for backend/routes/equipment.py — edit, preload, API endpoint."""

from unittest.mock import MagicMock, patch


def _make_cursor(fetchall_result=None, fetchone_result=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall_result if fetchall_result is not None else []
    cursor.fetchone.return_value = fetchone_result
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _csrf(client):
    with client.session_transaction() as sess:
        return sess['_csrf_token']


# ---------------------------------------------------------------------------
# GET /sprzet/<id>/edytuj
# ---------------------------------------------------------------------------

class TestEquipmentEditRoute:
    @patch('backend.routes.equipment.render_template')
    @patch('backend.routes.equipment.get_vehicles_cached')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_edit_get_renders_form(self, mock_db, mock_cur_fn, mock_vehicles, mock_render, admin_client):
        mock_db.return_value = MagicMock()
        item = {'id': 5, 'name': 'Torba R1', 'vehicle_id': 1, 'vname': 'GBA',
                'quantity': 1, 'unit': 'szt', 'category': 'Ratownictwo medyczne', 'notes': ''}
        mock_cur = _make_cursor(fetchone_result=item)
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_render.return_value = 'edit-page'

        response = admin_client.get('/sprzet/5/edytuj')

        assert response.status_code == 200
        assert response.data == b'edit-page'
        assert mock_render.call_args.args[0] == 'equipment_edit.html'

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_edit_get_not_found_redirects(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone_result=None)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.get('/sprzet/999/edytuj')
        assert response.status_code == 302

    def test_edit_get_non_admin_gets_403(self, authenticated_client):
        response = authenticated_client.get('/sprzet/5/edytuj')
        assert response.status_code == 403

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_edit_post_updates_equipment(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        item = {'id': 5, 'name': 'Torba R1', 'vehicle_id': 1, 'vname': 'GBA',
                'quantity': 1, 'unit': 'szt', 'category': 'Ratownictwo medyczne', 'notes': ''}
        mock_cur = _make_cursor(fetchone_result=item)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/5/edytuj', data={
            '_csrf_token': _csrf(admin_client),
            'name': 'Torba R1 updated',
            'quantity': '3',
            'unit': 'szt',
            'category': 'Ratownictwo medyczne',
            'notes': 'Updated',
        })

        assert response.status_code == 302
        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once()


# ---------------------------------------------------------------------------
# POST /sprzet/<id>/usun — extended
# ---------------------------------------------------------------------------

class TestEquipmentDeleteExtended:
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_delete_not_found_redirects(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone_result=None)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/999/usun', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302

    def test_delete_non_admin_gets_403(self, authenticated_client):
        response = authenticated_client.post('/sprzet/5/usun', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /sprzet/<id>/preload
# ---------------------------------------------------------------------------

class TestEquipmentPreload:
    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_preload_success(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        # First fetchone: vehicle exists; fetchall: existing equipment
        mock_cur.fetchone.return_value = {'id': 1}
        mock_cur.fetchall.return_value = []  # no existing equipment
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/1/preload', data={
            '_csrf_token': _csrf(admin_client),
        })

        assert response.status_code == 302
        mock_conn.commit.assert_called_once()
        mock_cur.executemany.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_preload_vehicle_not_found(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone_result=None)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/999/preload', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302

    def test_preload_non_admin_gets_403(self, authenticated_client):
        response = authenticated_client.post('/sprzet/1/preload', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 403

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_preload_skips_existing_equipment(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur.fetchone.return_value = {'id': 1}
        # All Ducato items already exist
        from backend.routes.equipment import DUCATO_EQUIPMENT
        mock_cur.fetchall.return_value = [{'name': name} for name, _, _, _ in DUCATO_EQUIPMENT]
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/1/preload', data={
            '_csrf_token': _csrf(admin_client),
        })

        assert response.status_code == 302
        mock_conn.commit.assert_called_once()
        # No executemany since everything already exists
        mock_cur.executemany.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/vehicle/<id>/equipment
# ---------------------------------------------------------------------------

class TestEquipmentApiEndpoint:
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_api_returns_json_list(self, mock_db, mock_cur_fn, authenticated_client):
        mock_db.return_value = MagicMock()
        items = [
            {'id': 1, 'name': 'Torba R1', 'quantity': 1, 'unit': 'szt', 'category': 'Ratownictwo medyczne'},
            {'id': 2, 'name': 'Piła', 'quantity': 1, 'unit': 'szt', 'category': 'Pilarstwo'},
        ]
        mock_cur = _make_cursor(fetchall_result=items)
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.get('/api/vehicle/1/equipment')

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['name'] == 'Torba R1'

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_api_empty_list(self, mock_db, mock_cur_fn, authenticated_client):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchall_result=[])
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.get('/api/vehicle/999/equipment')

        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_api_requires_login(self, client):
        response = client.get('/api/vehicle/1/equipment')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


# ---------------------------------------------------------------------------
# POST /sprzet/dodaj — extended validation
# ---------------------------------------------------------------------------

class TestEquipmentAddExtended:
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_add_missing_name_flashes_error(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()

        response = admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '1',
            'name': '',
        })
        assert response.status_code == 302

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_add_missing_vehicle_flashes_error(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()

        response = admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '',
            'name': 'Something',
        })
        assert response.status_code == 302

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_add_invalid_category_defaults_to_pozostale(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '1',
            'name': 'Nowy sprzęt',
            'category': 'InvalidCategory',
            'quantity': '1',
        })
        assert response.status_code == 302
        _, params = mock_cur.execute.call_args.args
        assert params[4] == 'Pozostałe'

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_add_invalid_quantity_defaults_to_1(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '1',
            'name': 'Nowy sprzęt',
            'category': 'Pozostałe',
            'quantity': 'abc',
        })
        assert response.status_code == 302
        _, params = mock_cur.execute.call_args.args
        assert params[2] == 1  # quantity defaults to 1

    def test_equipment_add_requires_admin(self, authenticated_client):
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/sprzet/dodaj', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'name': 'Torba R1',
        })

        assert response.status_code == 403
