from flask import request, jsonify, session, current_app
from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import login_required


class ValidationError(Exception):
    """Raised when request data fails validation."""


def _json_error(message, status_code):
    return jsonify({'success': False, 'message': message}), status_code


def _get_active_vehicle(cur, vehicle_id):
    """Zwraca pojazd jeśli istnieje i jest aktywny, inaczej None."""
    try:
        vid = int(vehicle_id)
    except (TypeError, ValueError):
        return None
    cur.execute("SELECT id FROM vehicles WHERE id = %s AND active = 1", (vid,))
    return cur.fetchone()


def register_routes(app):

    @app.route('/api/vehicle/<int:vid>/last_km', endpoint='api_vehicle_last_km')
    @login_required
    def api_vehicle_last_km(vid):
        conn = get_db()
        cur = get_cursor(conn)
        try:
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
        finally:
            cur.close()

        trip_km = trip_row['km'] if trip_row and trip_row['km'] else None
        fuel_km = fuel_row['km'] if fuel_row and fuel_row['km'] else None
        trip_dt = trip_row['dt'] if trip_row and trip_row['dt'] else None
        fuel_dt = fuel_row['dt'] if fuel_row and fuel_row['dt'] else None

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

        days_ago = None
        if dt:
            try:
                days_ago = (date.today() - date.fromisoformat(dt)).days
            except ValueError:
                pass

        return jsonify({'km': km, 'date': dt, 'days_ago': days_ago})

    @app.route('/api/drivers', endpoint='api_drivers')
    @login_required
    def api_drivers():
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('''
                SELECT DISTINCT driver FROM (
                    SELECT driver FROM trips WHERE date >= %s
                    UNION
                    SELECT driver FROM fuel WHERE date >= %s
                ) AS combined ORDER BY driver ASC
            ''', (cutoff, cutoff))
            rows = cur.fetchall()
        finally:
            cur.close()
        return jsonify([r['driver'] for r in rows])

    @app.route('/api/trips', methods=['POST'], endpoint='api_add_trip')
    @login_required
    def api_add_trip():
        f = request.form
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicle = _get_active_vehicle(cur, f.get('vehicle_id'))
            if not vehicle:
                raise ValidationError('Nieprawidłowy lub nieaktywny pojazd.')

            purpose_sel = f.get('purpose_select', '').strip()
            if purpose_sel == '__inne__':
                purpose = f.get('purpose_custom', '').strip()
            else:
                purpose = purpose_sel or f.get('purpose', '').strip()

            if not purpose:
                raise ValidationError('Cel wyjazdu jest wymagany.')

            driver = f.get('driver', '').strip()
            if not driver:
                raise ValidationError('Kierowca jest wymagany.')

            cur.execute('''
                INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                vehicle['id'], f['date'], driver,
                f.get('odo_start') or None, f.get('odo_end') or None,
                purpose, f.get('notes', '').strip(),
                session['username']
            ))
            conn.commit()
        except ValidationError as exc:
            conn.rollback()
            return _json_error(str(exc), 400)
        except Exception:
            conn.rollback()
            current_app.logger.exception('Trip API error')
            return _json_error('Nie udało się zapisać wyjazdu. Spróbuj ponownie.', 500)
        finally:
            cur.close()

        return jsonify({'success': True, 'message': '✓ Wyjazd zapisany'})

    @app.route('/api/fuel', methods=['POST'], endpoint='api_add_fuel')
    @login_required
    def api_add_fuel():
        f = request.form
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicle = _get_active_vehicle(cur, f.get('vehicle_id'))
            if not vehicle:
                raise ValidationError('Nieprawidłowy lub nieaktywny pojazd.')

            liters = (f.get('liters') or '').strip()
            if not liters:
                raise ValidationError('Podaj ilość paliwa.')

            driver = f.get('driver', '').strip()
            if not driver:
                raise ValidationError('Kierowca jest wymagany.')

            cur.execute('''
                INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                vehicle['id'], f['date'], driver,
                f.get('odometer') or None,
                liters, f.get('cost') or None,
                f.get('notes', '').strip(), session['username']
            ))
            conn.commit()
        except ValidationError as exc:
            conn.rollback()
            return _json_error(str(exc), 400)
        except Exception:
            conn.rollback()
            current_app.logger.exception('Fuel API error')
            return _json_error('Nie udało się zapisać tankowania. Spróbuj ponownie.', 500)
        finally:
            cur.close()

        return jsonify({'success': True, 'message': '✓ Tankowanie zapisane'})

    @app.route('/api/maintenance', methods=['POST'], endpoint='api_add_maintenance')
    @login_required
    def api_add_maintenance():
        f = request.form
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicle = _get_active_vehicle(cur, f.get('vehicle_id'))
            if not vehicle:
                raise ValidationError('Nieprawidłowy lub nieaktywny pojazd.')

            description = f.get('description', '').strip()
            if not description:
                raise ValidationError('Opis jest wymagany.')

            priority = f.get('priority', 'medium')
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'

            status = f.get('status', 'pending')
            if status not in ('pending', 'completed'):
                status = 'pending'

            cur.execute('''
                INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                vehicle['id'], f['date'],
                f.get('odometer') or None,
                description,
                f.get('cost') or None,
                f.get('notes', '').strip(),
                session['username'],
                status, priority,
                f.get('due_date') or None,
            ))
            conn.commit()
        except ValidationError as exc:
            conn.rollback()
            return _json_error(str(exc), 400)
        except Exception:
            conn.rollback()
            current_app.logger.exception('Maintenance API error')
            return _json_error('Nie udało się zapisać wpisu. Spróbuj ponownie.', 500)
        finally:
            cur.close()

        return jsonify({'success': True, 'message': '✓ Wpis serwisowy zapisany'})
