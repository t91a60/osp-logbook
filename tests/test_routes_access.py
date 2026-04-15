"""Tests for the /health endpoint and admin/equipment route access control."""

from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    """Test the /health endpoint."""

    @patch('app.check_db_health')
    def test_health_ok(self, mock_check, client):
        """Healthy DB returns 200 OK."""
        mock_check.return_value = True
        response = client.get('/health')
        assert response.status_code == 200
        assert response.data == b'OK'

    @patch('app.check_db_health')
    def test_health_db_error(self, mock_check, client):
        """Unhealthy DB returns 500."""
        mock_check.return_value = False
        response = client.get('/health')
        assert response.status_code == 500
        assert b'DB ERROR' in response.data


class TestEquipmentAccessControl:
    """Test that equipment routes require proper authentication."""

    def test_equipment_list_requires_login(self, client):
        response = client.get('/sprzet')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    def test_equipment_add_requires_admin(self, authenticated_client):
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']
        response = authenticated_client.post('/sprzet/dodaj', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'name': 'Test',
        })
        assert response.status_code == 403

    def test_equipment_edit_requires_admin(self, authenticated_client):
        response = authenticated_client.get('/sprzet/1/edytuj')
        assert response.status_code == 403

    def test_equipment_delete_requires_admin(self, authenticated_client):
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']
        response = authenticated_client.post('/sprzet/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 403

    def test_equipment_preload_requires_admin(self, authenticated_client):
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']
        response = authenticated_client.post('/sprzet/1/preload', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 403


class TestEquipmentCategories:
    """Test equipment module constants."""

    def test_categories_list(self):
        from backend.routes.equipment import CATEGORIES
        assert len(CATEGORIES) > 0
        assert 'Pozostałe' in CATEGORIES
        assert 'Hydraulika' in CATEGORIES

    def test_ducato_equipment_list(self):
        from backend.routes.equipment import DUCATO_EQUIPMENT
        assert len(DUCATO_EQUIPMENT) > 0
        # Each entry should be a tuple of (name, qty, unit, category)
        for item in DUCATO_EQUIPMENT:
            assert len(item) == 4
            assert isinstance(item[0], str)
            assert isinstance(item[1], int)


class TestMoreRoute:
    """Test /wiecej route access control."""

    def test_more_requires_login(self, client):
        response = client.get('/wiecej')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestLogsAccessControl:
    """Test /logs route access control."""

    def test_logs_requires_login(self, client):
        response = client.get('/logs')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    def test_logs_requires_admin(self, authenticated_client):
        response = authenticated_client.get('/logs')
        assert response.status_code == 403


class TestMaintenanceAccessControl:
    """Test /serwis route access."""

    def test_maintenance_requires_login(self, client):
        response = client.get('/serwis')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestTripsAccessControl:
    """Test /wyjazdy route access."""

    def test_trips_requires_login(self, client):
        response = client.get('/wyjazdy')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestFuelAccessControl:
    """Test /tankowania route access."""

    def test_fuel_requires_login(self, client):
        response = client.get('/tankowania')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestReportAccessControl:
    """Test /raport route access."""

    def test_report_requires_login(self, client):
        response = client.get('/raport')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')
