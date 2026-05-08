from flask import Response, request, jsonify, session, current_app
from datetime import date

from backend.db import get_db, get_cursor
from backend.helpers import (
    login_required,
    normalize_iso_date,
    parse_trip_equipment_form,
    get_active_vehicle,
    ensure_non_empty_text,
    validate_iso_date,
    parse_positive_int_field,
    parse_positive_float_field,
    validate_odometer_range,
)
from backend.services.core_service import TripService, VehicleService
from backend.services.cache_service import get_or_set
from backend.helpers import ValidationError


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({'success': False, 'message': message}), status_code


def _validate_or_raise(callable_obj, *args):
    try:
        return callable_obj(*args)
    except ValueError as exc:
        raise ValidationError(str(exc))


def _get_active_vehicle(cur, vehicle_id: str | int | None) -> dict | None:
    return get_active_vehicle(cur, vehicle_id)


def _optional_int(value: str | int | None, field_name: str) -> int | None:
    try:
        return parse_positive_int_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc))


def _optional_float(value: str | float | None, field_name: str) -> float | None:
    try:
        return parse_positive_float_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc))


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
                purpose = _validate_or_raise(ensure_non_empty_text, f.get('purpose_custom'), 'Cel wyjazdu')
            else:
                purpose = _validate_or_raise(ensure_non_empty_text, purpose_sel or f.get('purpose'), 'Cel wyjazdu')

            driver = _validate_or_raise(ensure_non_empty_text, f.get('driver'), 'Kierowca')
            trip_date = _validate_or_raise(validate_iso_date, f.get('date'), 'Data')

            odo_start = _optional_int(f.get('odo_start'), 'Km start')
            odo_end = _optional_int(f.get('odo_end'), 'Km koniec')
            validate_odometer_range(odo_start, odo_end)

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

            liters_float = _optional_float(f.get('liters'), 'Litry')
            if liters_float is None:
                raise ValidationError('Podaj ilość paliwa.')

            driver = _validate_or_raise(ensure_non_empty_text, f.get('driver'), 'Kierowca')
            fuel_date = _validate_or_raise(validate_iso_date, f.get('date'), 'Data')
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

            description = _validate_or_raise(ensure_non_empty_text, f.get('description'), 'Opis')
            maintenance_date = _validate_or_raise(validate_iso_date, f.get('date'), 'Data')

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
