from flask import render_template, make_response, current_app
from datetime import date
from backend.db import get_db, get_cursor
from backend.helpers import login_required


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
        conn = get_db()
        cur = get_cursor(conn)
        try:
            # Jedno zapytanie CTE zamiast N+1 pętli po pojazdach.
            # Zwraca dla każdego aktywnego pojazdu:
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
                WHERE v.active = 1
                ORDER BY v.name
            ''')
            vehicles_raw = cur.fetchall()

            vehicle_cards = []
            today = date.today()
            for v in vehicles_raw:
                days_ago = None
                if v['last_trip_date']:
                    try:
                        days_ago = (today - date.fromisoformat(v['last_trip_date'])).days
                    except ValueError:
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

            cur.execute('SELECT COUNT(*) AS count FROM trips')
            trips_count = cur.fetchone()['count']
            cur.execute('SELECT COUNT(*) AS count FROM fuel')
            fuel_count = cur.fetchone()['count']
            cur.execute('SELECT COUNT(*) AS count FROM maintenance')
            maint_count = cur.fetchone()['count']

            # vehicles_raw potrzebne dla selektora — pobierz wszystkie aktywne
            cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
            vehicles_all = cur.fetchall()
        finally:
            cur.close()

        stats = dict(trips=trips_count, fuel=fuel_count, maintenance=maint_count)

        return render_template('dashboard.html',
                               vehicles=vehicles_all,
                               vehicle_cards=vehicle_cards,
                               recent_trips=recent_trips,
                               recent_fuel=recent_fuel,
                               stats=stats,
                               today=today.isoformat())
