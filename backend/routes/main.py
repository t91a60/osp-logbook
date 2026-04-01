from flask import Blueprint, render_template, make_response, current_app
from datetime import date
from backend.db import get_db, get_cursor
from backend.helpers import login_required, normalize_iso_date, days_since_iso_date

main_bp = Blueprint('main', __name__)

@main_bp.route('/sw.js', endpoint='sw')
def sw():
    response = make_response(current_app.send_static_file('sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@main_bp.route('/', endpoint='dashboard')
@login_required
def dashboard():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        WITH TripDetails AS (
            SELECT vehicle_id, 
                   MAX(odo_end) as max_trip_km, 
                   MAX(date) as max_trip_dt
            FROM trips 
            WHERE odo_end IS NOT NULL
            GROUP BY vehicle_id
        ),
        FuelDetails AS (
            SELECT vehicle_id, 
                   MAX(odometer) as max_fuel_km, 
                   MAX(date) as max_fuel_dt
            FROM fuel 
            WHERE odometer IS NOT NULL
            GROUP BY vehicle_id
        ),
        LastTripInfo AS (
            SELECT vehicle_id,
                   MAX(date) as abs_last_trip_dt
            FROM trips
            GROUP BY vehicle_id
        )
        SELECT v.id, v.name, v.plate, v.type,
               t.max_trip_km, t.max_trip_dt,
               f.max_fuel_km, f.max_fuel_dt,
               lt.abs_last_trip_dt
        FROM vehicles v
        LEFT JOIN TripDetails t ON v.id = t.vehicle_id
        LEFT JOIN FuelDetails f ON v.id = f.vehicle_id
        LEFT JOIN LastTripInfo lt ON v.id = lt.vehicle_id
        WHERE v.active = 1
        ORDER BY v.name
    ''')
    vehicles_with_stats = cur.fetchall()

    vehicle_cards = []
    vehicles_raw = []
    for v in vehicles_with_stats:
        vehicles_raw.append(v)
        trip_km = v['max_trip_km']
        fuel_km = v['max_fuel_km']
        trip_dt = normalize_iso_date(v['max_trip_dt']) if v['max_trip_dt'] else None
        fuel_dt = normalize_iso_date(v['max_fuel_dt']) if v['max_fuel_dt'] else None
        last_trip_dt = normalize_iso_date(v['abs_last_trip_dt']) if v['abs_last_trip_dt'] else None

        last_km = None
        if trip_km is not None and fuel_km is not None:
            last_km = trip_km if (trip_dt or '') >= (fuel_dt or '') else fuel_km
        elif trip_km is not None:
            last_km = trip_km
        elif fuel_km is not None:
            last_km = fuel_km
        
        vehicle_cards.append({
            'id': v['id'],
            'name': v['name'],
            'plate': v['plate'],
            'type': v['type'],
            'last_km': last_km,
            'last_trip_date': last_trip_dt,
            'days_ago': days_since_iso_date(last_trip_dt)
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