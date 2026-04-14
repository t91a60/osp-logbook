from flask import render_template, make_response, current_app
from datetime import date
from backend.db import get_db, get_cursor
from backend.helpers import login_required, normalize_iso_date
from backend.services.cache_service import get_or_set


def register_routes(app):
    @app.route('/sw.js', endpoint='sw')
    def sw():
        response = make_response(current_app.send_static_file('sw.js'))
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/', endpoint='dashboard')
    @login_required
    def dashboard():
        def _load_dashboard_data():
            conn = get_db()
            cur = get_cursor(conn)
            try:
                # Jedno zapytanie CTE zamiast N+1 pętli po pojazdach.
                # Zwraca dla każdego pojazdu:
                #   - ostatnie znane km (max z trips.odo_end i fuel.odometer)
                #   - datę ostatniego wyjazdu
                cur.execute('''
                    WITH trip_max AS (
                        SELECT vehicle_id,
                               MAX(odo_end)  AS last_km,
                               MAX(date)     AS last_km_date
                        FROM trips
                        WHERE odo_end IS NOT NULL
                        GROUP BY vehicle_id
                    ),
                    fuel_max AS (
                        SELECT vehicle_id,
                               MAX(odometer) AS last_km,
                               MAX(date)     AS last_km_date
                        FROM fuel
                        WHERE odometer IS NOT NULL
                        GROUP BY vehicle_id
                    ),
                    last_trip_date AS (
                        SELECT vehicle_id, MAX(date) AS last_trip_date
                        FROM trips
                        GROUP BY vehicle_id
                    )
                    SELECT
                        v.id, v.name, v.plate, v.type,
                        CASE
                            WHEN tm.last_km IS NULL THEN fm.last_km
                            WHEN fm.last_km IS NULL THEN tm.last_km
                            WHEN (tm.last_km_date >= fm.last_km_date) THEN tm.last_km
                            ELSE fm.last_km
                        END AS last_km,
                        ltd.last_trip_date
                    FROM vehicles v
                    LEFT JOIN trip_max      tm  ON tm.vehicle_id = v.id
                    LEFT JOIN fuel_max      fm  ON fm.vehicle_id = v.id
                    LEFT JOIN last_trip_date ltd ON ltd.vehicle_id = v.id
                    ORDER BY v.name
                ''')
                vehicles_raw = cur.fetchall()

                vehicle_cards = []
                today_local = date.today()
                for v in vehicles_raw:
                    days_ago = None
                    if v['last_trip_date']:
                        try:
                            normalized_last_trip_date = normalize_iso_date(v['last_trip_date'])
                            if normalized_last_trip_date is None:
                                raise ValueError
                            days_ago = (today_local - date.fromisoformat(normalized_last_trip_date)).days
                        except (TypeError, ValueError):
                            pass
                    vehicle_cards.append({
                        'id':              v['id'],
                        'name':            v['name'],
                        'plate':           v['plate'],
                        'type':            v['type'],
                        'last_km':         v['last_km'],
                        'last_trip_date':  v['last_trip_date'],
                        'days_ago':        days_ago,
                    })

                cur.execute('''
                    SELECT t.*, v.name AS vname
                    FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
                    ORDER BY t.date DESC, t.created_at DESC LIMIT 6
                ''')
                recent_trips = cur.fetchall()

                cur.execute('''
                    SELECT f.*, v.name AS vname
                    FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id
                    ORDER BY f.date DESC, f.created_at DESC LIMIT 4
                ''')
                recent_fuel = cur.fetchall()

                cur.execute('''
                    SELECT
                        (SELECT COUNT(*) FROM trips) AS trips_count,
                        (SELECT COUNT(*) FROM fuel) AS fuel_count,
                        (SELECT COUNT(*) FROM maintenance) AS maint_count
                ''')
                stats_row = cur.fetchone()
                stats = {
                    'trips': stats_row['trips_count'],
                    'fuel': stats_row['fuel_count'],
                    'maintenance': stats_row['maint_count'],
                }
                return {
                    'vehicle_cards': vehicle_cards,
                    'recent_trips': recent_trips,
                    'recent_fuel': recent_fuel,
                    'stats': stats,
                }
            finally:
                cur.close()

        payload = get_or_set('dashboard:snapshot:v1', ttl_seconds=20, loader=_load_dashboard_data)
        today = date.today()

        return render_template('dashboard.html',
                               vehicle_cards=payload['vehicle_cards'],
                               recent_trips=payload['recent_trips'],
                               recent_fuel=payload['recent_fuel'],
                               stats=payload['stats'],
                               today=today.isoformat())
