"""Tests for backend/routes/maintenance.py."""

from unittest.mock import MagicMock, patch

from backend.domain.exceptions import ForbiddenError, NotFoundError
from psycopg2 import IntegrityError


def _csrf(client):
    with client.session_transaction() as sess:
        return sess['_csrf_token']


class TestMaintenanceGetRoute:
    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.GetMaintenanceUseCase.execute')
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
    @patch('backend.routes.maintenance.GetMaintenanceUseCase.execute')
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
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_post_missing_vehicle_returns_400(self, mock_vehicles, authenticated_client):
        mock_vehicles.return_value = []
        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302

    @patch('backend.routes.maintenance.AddMaintenanceUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_post_valid_data_creates_entry(self, mock_vehicles, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

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
        mock_execute.assert_called_once()

    @patch('backend.routes.maintenance.AddMaintenanceUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_post_missing_description_returns_400(self, mock_vehicles, mock_execute, authenticated_client):
        from backend.domain.exceptions import ValidationError
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_execute.side_effect = ValidationError('Opis')

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': '',
        })

        assert response.status_code == 302

    @patch('backend.routes.maintenance.AddMaintenanceUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_post_handles_integrity_error(self, mock_vehicles, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_execute.side_effect = IntegrityError()

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302


class TestMaintenanceEditRoute:
    @patch('backend.routes.maintenance.GetMaintenanceByIdUseCase.execute')
    def test_edit_get_missing_entry(self, mock_get_by_id, authenticated_client):
        mock_get_by_id.return_value = None

        response = authenticated_client.get('/serwis/10/edytuj')

        assert response.status_code == 302
        assert '/serwis' in response.headers['Location']

    @patch('backend.routes.maintenance.GetMaintenanceByIdUseCase.execute')
    def test_edit_get_forbidden(self, mock_get_by_id, authenticated_client):
        mock_get_by_id.return_value = {'id': 10, 'added_by': 'other'}

        response = authenticated_client.get('/serwis/10/edytuj')

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/')

    @patch('backend.routes.maintenance.GetMaintenanceByIdUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_edit_post_missing_vehicle(self, mock_vehicles, mock_get_by_id, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_by_id.return_value = {'id': 10, 'added_by': 'testuser'}

        response = authenticated_client.post('/serwis/10/edytuj', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302

    @patch('backend.routes.maintenance.EditMaintenanceUseCase.execute')
    @patch('backend.routes.maintenance.GetMaintenanceByIdUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_edit_post_handles_not_found(self, mock_vehicles, mock_get_by_id, mock_edit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_by_id.return_value = {'id': 10, 'added_by': 'testuser'}
        mock_edit.side_effect = NotFoundError('missing')

        response = authenticated_client.post('/serwis/10/edytuj', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302

    @patch('backend.routes.maintenance.EditMaintenanceUseCase.execute')
    @patch('backend.routes.maintenance.GetMaintenanceByIdUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_edit_post_handles_integrity_error(self, mock_vehicles, mock_get_by_id, mock_edit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_by_id.return_value = {'id': 10, 'added_by': 'testuser'}
        mock_edit.side_effect = IntegrityError()

        response = authenticated_client.post('/serwis/10/edytuj', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302

    @patch('backend.routes.maintenance.EditMaintenanceUseCase.execute')
    @patch('backend.routes.maintenance.GetMaintenanceByIdUseCase.execute')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    def test_edit_post_success(self, mock_vehicles, mock_get_by_id, mock_edit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_by_id.return_value = {'id': 10, 'added_by': 'testuser'}

        response = authenticated_client.post('/serwis/10/edytuj', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })

        assert response.status_code == 302
        mock_edit.assert_called_once()


class TestMaintenanceMutationRoutes:
    @patch('backend.routes.maintenance.CompleteMaintenanceUseCase.execute')
    def test_complete_marks_entry_done(self, mock_complete, authenticated_client):

        response = authenticated_client.post('/serwis/1/complete', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302
        mock_complete.assert_called_once()
        cmd = mock_complete.call_args.args[0]
        assert cmd.entry_id == 1

    @patch('backend.routes.maintenance.CreateNextMaintenanceUseCase.execute')
    def test_next_creates_followup_entry(self, mock_create_next, authenticated_client):
        response = authenticated_client.post('/serwis/1/next', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302
        mock_create_next.assert_called_once()
        cmd = mock_create_next.call_args.args[0]
        assert cmd.entry_id == 1
        assert cmd.added_by == 'testuser'

    @patch('backend.routes.maintenance.CompleteMaintenanceUseCase.execute')
    def test_complete_handles_not_found(self, mock_complete, authenticated_client):
        mock_complete.side_effect = NotFoundError('missing')

        response = authenticated_client.post('/serwis/1/complete', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302

    @patch('backend.routes.maintenance.CompleteMaintenanceUseCase.execute')
    def test_complete_forbidden_returns_403(self, mock_complete, authenticated_client):
        mock_complete.side_effect = ForbiddenError('forbidden')

        response = authenticated_client.post('/serwis/1/complete', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 403

    @patch('backend.routes.maintenance.CreateNextMaintenanceUseCase.execute')
    def test_next_handles_not_found(self, mock_next, authenticated_client):
        mock_next.side_effect = NotFoundError('missing')

        response = authenticated_client.post('/serwis/1/next', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302

    @patch('backend.routes.maintenance.CreateNextMaintenanceUseCase.execute')
    def test_next_forbidden_returns_403(self, mock_next, authenticated_client):
        mock_next.side_effect = ForbiddenError('forbidden')

        response = authenticated_client.post('/serwis/1/next', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 403

    @patch('backend.routes.maintenance.DeleteMaintenanceUseCase.execute')
    def test_delete_handles_not_found(self, mock_delete, authenticated_client):
        mock_delete.side_effect = NotFoundError('missing')

        response = authenticated_client.post('/serwis/1/usun', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302

    @patch('backend.routes.maintenance.DeleteMaintenanceUseCase.execute')
    def test_delete_handles_forbidden(self, mock_delete, authenticated_client):
        mock_delete.side_effect = ForbiddenError('forbidden')

        response = authenticated_client.post('/serwis/1/usun', data={'_csrf_token': _csrf(authenticated_client)})

        assert response.status_code == 302
