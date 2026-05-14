"""Tests for low-coverage route modules: logs and main dashboard/sw endpoints."""

from datetime import date
from unittest.mock import patch, MagicMock


class TestLogsRoute:
    @patch('backend.routes.logs.render_template')
    @patch('backend.routes.logs.get_cursor')
    @patch('backend.routes.logs.get_db')
    def test_logs_list_clamps_page_and_applies_offset(self, mock_get_db, mock_get_cursor, mock_render, admin_client, monkeypatch):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'count': 3}
        mock_cur.fetchall.return_value = [{'id': 1}]
        mock_render.return_value = 'logs-page'

        monkeypatch.setitem(admin_client.application.config, 'LOGS_PAGE_SIZE', 2)
        response = admin_client.get('/logs?page=99')

        assert response.status_code == 200
        assert response.data == b'logs-page'
        assert mock_cur.execute.call_args_list[1].args[1] == (2, 2)
        context = mock_render.call_args.kwargs
        assert context['page'] == 2
        assert context['total_pages'] == 2
        assert context['total'] == 3

    @patch('backend.routes.logs.render_template')
    @patch('backend.routes.logs.get_cursor')
    @patch('backend.routes.logs.get_db')
    def test_logs_list_invalid_page_size_falls_back_to_default(self, mock_get_db, mock_get_cursor, mock_render, admin_client, monkeypatch):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'count': 0}
        mock_cur.fetchall.return_value = []
        mock_render.return_value = 'logs-page'

        monkeypatch.setitem(admin_client.application.config, 'LOGS_PAGE_SIZE', 'abc')
        response = admin_client.get('/logs?page=-3')

        assert response.status_code == 200
        assert mock_cur.execute.call_args_list[1].args[1] == (50, 0)
        context = mock_render.call_args.kwargs
        assert context['page'] == 1
        assert context['total_pages'] == 1


class TestMainRoutes:
    def test_sw_headers(self, client):
        response = client.get('/sw.js')
        assert response.status_code == 200
        assert response.headers.get('Content-Type', '').startswith('application/javascript')
        assert response.headers.get('Service-Worker-Allowed') == '/'
        cache_control = response.headers.get('Cache-Control', '')
        assert 'no-cache' in cache_control
        assert 'no-store' in cache_control
        assert 'must-revalidate' in cache_control

    @patch('backend.routes.main.render_template')
    @patch('backend.routes.main.GetDashboardUseCase.execute')
    @patch('backend.routes.main.get_or_set')
    def test_dashboard_loader_builds_cards_and_stats(
        self,
        mock_get_or_set,
        mock_execute,
        mock_render,
        authenticated_client,
    ):
        from backend.application.dashboard import (
            DashboardResult,
            DashboardStats,
            VehicleCard,
        )
        mock_execute.return_value = DashboardResult(
            vehicle_cards=[
                VehicleCard(
                    id=1, name='GBA', plate='KR1', type='gaśniczy',
                    last_km=12345, last_trip_date=date.today().isoformat(), days_ago=0,
                ),
                VehicleCard(
                    id=2, name='SLR', plate='KR2', type='ratowniczy',
                    last_km=None, last_trip_date=None, days_ago=None,
                ),
            ],
            recent_trips=[{'id': 10}],
            recent_fuel=[{'id': 20}],
            stats=DashboardStats(trips=7, fuel=5, maintenance=3),
            generated_on=date.today().isoformat(),
        )
        mock_render.return_value = 'dashboard-page'

        def passthrough_cache(_key, ttl_seconds, loader):
            assert ttl_seconds == 20
            return loader()

        mock_get_or_set.side_effect = passthrough_cache

        response = authenticated_client.get('/')

        assert response.status_code == 200
        assert response.data == b'dashboard-page'
        context = mock_render.call_args.kwargs
        assert context['stats'] == {'trips': 7, 'fuel': 5, 'maintenance': 3}
        assert len(context['vehicle_cards']) == 2
        assert context['vehicle_cards'][0]['days_ago'] == 0
        assert context['vehicle_cards'][1]['days_ago'] is None
