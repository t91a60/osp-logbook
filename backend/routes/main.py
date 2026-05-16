"""
Main routes — dashboard and service worker.

The dashboard route delegates to GetDashboardUseCase which lives in the
application layer (no Flask).  The route itself remains thin:
  - Auth guard (@login_required)
  - Cache wrapper (get_or_set)
  - Template rendering
"""
import hashlib
import os

from flask import render_template, make_response, current_app
from datetime import date

from backend.helpers import login_required, normalize_iso_date
from backend.services.cache_service import get_or_set

# Application layer — imported lazily inside the view to support mocking in
# tests that patch get_db / get_cursor directly on this module (legacy mocks
# still pass because get_or_set is mocked to call the loader directly).
from backend.application.dashboard import GetDashboardUseCase


def register_routes(app):
    @app.route('/sw.js', endpoint='sw')
    def sw():
        static_root = os.path.realpath(os.path.join(current_app.root_path, 'static'))
        cache_assets = ['main.css', 'mobile.css', 'login.css', 'app.js', 'manifest.json']
        version_seed = []
        for asset_name in cache_assets:
            asset_path = os.path.realpath(os.path.join(static_root, asset_name))
            if asset_path.startswith(static_root + os.sep):
                try:
                    version_seed.append(f"{asset_name}:{int(os.path.getmtime(asset_path))}")
                except (OSError, ValueError):
                    version_seed.append(f"{asset_name}:0")
        sw_path = os.path.realpath(os.path.join(static_root, 'sw.js'))
        with open(sw_path, encoding='utf-8') as sw_file:
            sw_text = sw_file.read()

        version_hash = hashlib.sha1('|'.join(version_seed).encode('utf-8')).hexdigest()[:12]
        cache_name = f'osp-logbook-{version_hash}'
        response = make_response(sw_text.replace('__SW_CACHE_NAME__', cache_name))
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/', endpoint='dashboard')
    @login_required
    def dashboard():
        # get_or_set caches the DashboardResult for 20 s.
        # The loader returns a plain dict for cache serialisation compatibility.
        def _loader():
            result = GetDashboardUseCase.execute()
            # Convert frozen dataclasses to dicts for cache-layer compatibility
            # (the cache stores arbitrary Python objects in-process, so this is
            #  fine; we do it anyway so the template context keys are unchanged).
            return {
                'vehicle_cards': [
                    {
                        'id':             c.id,
                        'name':           c.name,
                        'plate':          c.plate,
                        'type':           c.type,
                        'last_km':        c.last_km,
                        'last_trip_date': c.last_trip_date,
                        'days_ago':       c.days_ago,
                    }
                    for c in result.vehicle_cards
                ],
                'recent_trips': result.recent_trips,
                'recent_fuel':  result.recent_fuel,
                'stats': {
                    'trips':       result.stats.trips,
                    'fuel':        result.stats.fuel,
                    'maintenance': result.stats.maintenance,
                },
            }

        payload = get_or_set('dashboard:snapshot:v1', ttl_seconds=20, loader=_loader)

        return render_template(
            'dashboard.html',
            vehicle_cards=payload['vehicle_cards'],
            recent_trips=payload['recent_trips'],
            recent_fuel=payload['recent_fuel'],
            stats=payload['stats'],
            today=date.today().isoformat(),
        )
