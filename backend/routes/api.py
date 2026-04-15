from flask import Response, request, jsonify, session, current_app
from datetime import date

from backend.db import get_db, get_cursor
from backend.helpers import login_required, normalize_iso_date, parse_trip_equipment_form
from backend.services.core_service import TripService, VehicleService
from backend.services.cache_service import get_or_set


class ValidationError(Exception):
    """Raised when request data fails validation."""


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({'success': False, 'message': message}), status_code


def _get_active_vehicle(cur, vehicle_id: str | int | None) -> dict | None:
    """Zwraca pojazd jeśli istnieje, inaczej None."""
    try:
        vid = int(vehicle_id)
    except (TypeError, ValueError):
        return None
    cur.execute("SELECT id FROM vehicles WHERE id = %s", (vid,))
    return cur.fetchone()


def _optional_int(value: str | int | None, field_name: str) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field_name} musi być liczbą całkowitą.')


def _optional_float(value: str | float | None, field_name: str) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field_name} musi być liczbą.')


def register_routes(app):
    from app import limiter

    @app.route('/api/vehicle/<int:vid>/last_km', endpoint='api_vehicle_last_km')
    @login_required
    @limiter.limit('120 per minute')
    def api_vehicle_last_km(vid):
        cache_key = f'api:last_km:{vid}'
        km, dt = get_or_set(
            cache_key,
            ttl_seconds=30,
            loader=lambda: VehicleService.get_last_km(vid),
        )

        days_ago = None
        if dt:
            try:
                days_ago = (date.today() - date.fromisoformat(normalize_iso_date(dt))).days
            except (TypeError, ValueError):
                pass

        return jsonify({'km': km, 'date': dt, 'days_ago': days_ago})

    @app.route('/api/drivers', endpoint='api_drivers')
    @login_required
    @limiter.limit('120 per minute')
    def api_drivers():
        drivers = get_or_set(
            'api:drivers:90d',
            ttl_seconds=300,
            loader=lambda: VehicleService.get_recent_drivers(days=90),
        )
        return jsonify(drivers)

    @app.route('/api/trips', methods=['POST'], endpoint='api_add_trip')
    @login_required
    @limiter.limit('60 per minute')
    def api_add_trip():
        f = request.form
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicle = _get_active_vehicle(cur, f.get('vehicle_id'))
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

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

            trip_date = f.get('date', '').strip()
            if not trip_date:
                raise ValidationError('Data jest wymagana.')

            odo_start = _optional_int(f.get('odo_start'), 'Km start')
            odo_end = _optional_int(f.get('odo_end'), 'Km koniec')

            try:
                equipment_used = parse_trip_equipment_form(request.form)
            except ValueError as exc:
                raise ValidationError(str(exc))

            TripService.add_trip(
                vehicle['id'],
                trip_date,
                driver,
                odo_start,
                odo_end,
                purpose,
                f.get('notes', '').strip(),
                session['username'],
                time_start=f.get('time_start') or None,
                time_end=f.get('time_end') or None,
                equipment_used=equipment_used or None,
            )
        except ValidationError as exc:
            return _json_error(str(exc), 400)
        except Exception:
            current_app.logger.exception('Trip API error')
            return _json_error('Nie udało się zapisać wyjazdu. Spróbuj ponownie.', 500)
        finally:
            cur.close()

        return jsonify({'success': True, 'message': '✓ Wyjazd zapisany'})

    @app.route('/api/fuel', methods=['POST'], endpoint='api_add_fuel')
    @login_required
    @limiter.limit('60 per minute')
    def api_add_fuel():
        f = request.form
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicle = _get_active_vehicle(cur, f.get('vehicle_id'))
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

            liters = (f.get('liters') or '').strip()
            if not liters:
                raise ValidationError('Podaj ilość paliwa.')

            driver = f.get('driver', '').strip()
            if not driver:
                raise ValidationError('Kierowca jest wymagany.')

            fuel_date = f.get('date', '').strip()
            if not fuel_date:
                raise ValidationError('Data jest wymagana.')

            liters_float = _optional_float(liters, 'Litry')
            if liters_float is None or liters_float <= 0:
                raise ValidationError('Podaj poprawną ilość paliwa.')

            cost = _optional_float(f.get('cost'), 'Koszt')
            odometer = _optional_int(f.get('odometer'), 'Stan km')

            cur.execute('''
                INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                vehicle['id'], fuel_date, driver,
                odometer,
                liters_float, cost,
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
    @limiter.limit('60 per minute')
    def api_add_maintenance():
        f = request.form
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicle = _get_active_vehicle(cur, f.get('vehicle_id'))
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

            description = f.get('description', '').strip()
            if not description:
                raise ValidationError('Opis jest wymagany.')

            maintenance_date = f.get('date', '').strip()
            if not maintenance_date:
                raise ValidationError('Data jest wymagana.')

            priority = f.get('priority', 'medium')
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'

            status = f.get('status', 'pending')
            if status not in ('pending', 'completed'):
                status = 'pending'

            odometer = _optional_int(f.get('odometer'), 'Stan km')
            cost = _optional_float(f.get('cost'), 'Koszt')

            cur.execute('''
                INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                vehicle['id'], maintenance_date,
                odometer,
                description,
                cost,
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
