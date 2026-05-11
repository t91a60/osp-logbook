"""Tests for backend/routes/maintenance.py."""

from unittest.mock import MagicMock, patch


def _csrf(client):
    with client.session_transaction() as sess:
        return sess['_csrf_token']


class TestMaintenanceGetRoute:
    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_get_renders_with_entries(self, mock_vehicles, mock_get_page, mock_render, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([{'id': 10}], 1, 1, 1)
        mock_render.return_value = 'maintenance-page'

        response = authenticated_client.get('/serwis')

        assert response.status_code == 200
        assert response.data == b'maintenance-page'
        assert mock_render.call_args.kwargs['vehicles'] == [{'id': 1, 'name': 'GBA'}]
        assert mock_render.call_args.kwargs['entries'] == [{'id': 10}]

    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_get_filters_by_status_and_vehicle(self, mock_vehicles, mock_get_page, mock_render, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'maintenance-page'

        response = authenticated_client.get('/serwis?status=overdue&vehicle_id=1')

        assert response.status_code == 200
        assert mock_render.call_args.kwargs['selected_status'] == 'overdue'
        assert mock_render.call_args.kwargs['selected_vehicle'] == '1'


class TestMaintenancePostRoute:
    @patch('backend.routes.maintenance.VehicleRepository.get_active')
    def test_post_missing_vehicle_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = None

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302

    @patch('backend.routes.maintenance.AuditService')
    @patch('backend.routes.maintenance.MaintenanceRepository')
    @patch('backend.routes.maintenance.VehicleRepository.get_active')
    def test_post_valid_data_creates_entry(self, mock_get_active, mock_repo, mock_audit, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Wymiana oleju',
            'odometer': '15000',
            'cost': '250.00',
            'priority': 'high',
            'status': 'pending',
        })

        assert response.status_code == 302
        mock_repo.add.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.routes.maintenance.VehicleRepository.get_active')
    def test_post_missing_description_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': '',
        })

        assert response.status_code == 302


class TestMaintenanceMutationRoutes:
    @patch('backend.routes.maintenance.MaintenanceRepository.complete')
    def test_complete_marks_entry_done(self, mock_complete, authenticated_client):
        mock_complete.return_value = {'id': 1, 'added_by': 'testuser'}

        response = authenticated_client.post('/serwis/1/complete', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302
        mock_complete.assert_called_once_with(1)

    @patch('backend.routes.maintenance.MaintenanceRepository.create_next')
    def test_next_creates_followup_entry(self, mock_create_next, authenticated_client):
        mock_create_next.return_value = {'id': 1, 'added_by': 'testuser'}

        response = authenticated_client.post('/serwis/1/next', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302
        mock_create_next.assert_called_once_with(1, added_by='testuser')