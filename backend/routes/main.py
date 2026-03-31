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
        cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
        vehicles_raw = cur.fetchall()

        vehicle_cards = []
        for v in vehicles_raw:
            vid = v['id']
            cur.execute(
                "SELECT MAX(odo_end) as km, MAX(date) as dt FROM trips WHERE vehicle_id = %s AND odo_end IS NOT NULL",
                (vid,)
            )
            trip_row = cur.fetchone()
            cur.execute(
                "SELECT MAX(odometer) as km, MAX(date) as dt FROM fuel WHERE vehicle_id = %s AND odometer IS NOT NULL",
                (vid,)
            )
            fuel_row = cur.fetchone()

            trip_km = trip_row['km'] if trip_row and trip_row['km'] else None
            fuel_km = fuel_row['km'] if fuel_row and fuel_row['km'] else None
            trip_dt = trip_row['dt'] if trip_row else None
            fuel_dt = fuel_row['dt'] if fuel_row else None

            last_km = None
            if trip_km is not None and fuel_km is not None:
                last_km = trip_km if (trip_dt or '') >= (fuel_dt or '') else fuel_km
            elif trip_km is not None:
                last_km = trip_km
            elif fuel_km is not None:
                last_km = fuel_km

            cur.execute(
                "SELECT MAX(date) as dt FROM trips WHERE vehicle_id = %s", (vid,)
            )
            last_trip_row = cur.fetchone()
            last_trip_dt = last_trip_row['dt'] if last_trip_row else None

            days_ago = None
            if last_trip_dt:
                try:
                    delta = date.today() - date.fromisoformat(last_trip_dt)
                    days_ago = delta.days
                except ValueError:
                    pass

            vehicle_cards.append({
                'id': v['id'],
                'name': v['name'],
                'plate': v['plate'],
                'type': v['type'],
                'last_km': last_km,
                'last_trip_date': last_trip_dt,
                'days_ago': days_ago,
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
        cur.execute('SELECT COUNT(*) FROM trips')
        trips_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM fuel')
        fuel_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM maintenance')
        maint_count = cur.fetchone()[0]
        cur.close()

        stats = dict(
            trips=trips_count,
            fuel=fuel_count,
            maintenance=maint_count,
        )

        return render_template('dashboard.html',
                               vehicles=vehicles_raw,
                               vehicle_cards=vehicle_cards,
                               recent_trips=recent_trips,
                               recent_fuel=recent_fuel,
                               stats=stats,
                               today=date.today().isoformat())