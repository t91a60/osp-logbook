from flask import url_for

from app import app


def test_critical_endpoints_registered():
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    expected = {
        'health',
        'dashboard',
        'login',
        'logout',
        'trips',
        'fuel',
        'maintenance',
        'report',
        'vehicles',
        'users',
        'delete_vehicle',
        'logs.logs_list',
        'api_add_trip',
        'api_add_fuel',
        'api_add_maintenance',
    }
    assert expected.issubset(endpoints)


def test_template_url_builders_do_not_break():
    with app.test_request_context():
        assert url_for('delete_vehicle', vid=1) == '/pojazdy/1/usun'
        assert url_for('delete_entry', kind='wyjazd', eid=10) == '/usun/wyjazd/10'
        assert url_for('report') == '/raport'
        assert url_for('logs.logs_list') == '/logs'
