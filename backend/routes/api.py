from flask import Blueprint, request, jsonify, session, current_app
from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import login_required, normalize_iso_date, days_since_iso_date

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/vehicle/<int:vid>/last_km', endpoint='api_vehicle_last_km')
@login_required
def api_vehicle_last_km(vid):
    conn = get_db()
    cur = get_cursor(conn)
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
    cur.close()

    trip_km = trip_row['km'] if trip_row and trip_row['km'] else None
    fuel_km = fuel_row['km'] if fuel_row and fuel_row['km'] else None
    trip_dt = normalize_iso_date(trip_row['dt']) if trip_row and trip_row['dt'] else None
    fuel_dt = normalize_iso_date(fuel_row['dt']) if fuel_row and fuel_row['dt'] else None

    km = None
    dt = None
    if trip_km is not None and fuel_km is not None:
        if (trip_dt or '') >= (fuel_dt or ''):
            km, dt = trip_km, trip_dt
        else:
            km, dt = fuel_km, fuel_dt
    elif trip_km is not None:
        km, dt = trip_km, trip_dt
    elif fuel_km is not None:
        km, dt = fuel_km, fuel_dt

    days_ago = days_since_iso_date(dt)

    return jsonify({'km': km, 'date': dt, 'days_ago': days_ago})

@api_bp.route('/api/drivers', endpoint='api_drivers')
@login_required
def api_drivers():
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT DISTINCT driver FROM (
            SELECT driver FROM trips WHERE date >= %s
            UNION
            SELECT driver FROM fuel WHERE date >= %s
        ) ORDER BY driver ASC
    ''', (cutoff, cutoff))
    rows = cur.fetchall()
    cur.close()
    return jsonify([r['driver'] for r in rows])

@api_bp.route('/api/trips', methods=['POST'], endpoint='api_add_trip')
@login_required
def api_add_trip():
    try:
        f = request.form
        purpose_sel = f.get('purpose_select', '').strip()
        if purpose_sel == '__inne__':
            purpose = f.get('purpose_custom', '').strip()
        else:
            purpose = purpose_sel or f.get('purpose', '').strip()

        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            f.get('odo_start') or None, f.get('odo_end') or None,
            purpose, f.get('notes', '').strip(),
            session['username']
        ))
        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': '✓ Wyjazd zapisany'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd: {str(e)}'}), 400

@api_bp.route('/api/fuel', methods=['POST'], endpoint='api_add_fuel')
@login_required
def api_add_fuel():
    try:
        f = request.form
        liters = (f.get('liters') or '').strip()
        if not liters:
            return jsonify({'success': False, 'message': 'Podaj ilość paliwa.'}), 400
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            f.get('odometer') or None,
            liters, f.get('cost') or None,
            f.get('notes', '').strip(), session['username']
        ))
        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': '✓ Tankowanie zapisane'})
    except Exception as e:
        current_app.logger.exception('Fuel API error: %s', e)
        return jsonify({'success': False, 'message': 'Nie udało się zapisać tankowania. Spróbuj ponownie.'}), 400

@api_bp.route('/api/maintenance', methods=['POST'], endpoint='api_add_maintenance')
@login_required
def api_add_maintenance():
    try:
        f = request.form
        priority = f.get('priority', 'medium')
        if priority not in ('low', 'medium', 'high'):
            priority = 'medium'

        status = f.get('status', 'pending')
        if status not in ('pending', 'completed'):
            status = 'pending'

        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            f['vehicle_id'], f['date'],
            f.get('odometer') or None,
            f['description'].strip(),
            f.get('cost') or None,
            f.get('notes', '').strip(),
            session['username'],
            status,
            priority,
            f.get('due_date') or None,
        ))
        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': '✓ Wpis serwisowy zapisany'})
    except Exception as e:
        current_app.logger.exception('Maintenance API error: %s', e)
        return jsonify({'success': False, 'message': 'Nie udało się zapisać wpisu.'}), 400