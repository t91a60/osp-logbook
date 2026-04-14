from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate, parse_positive_int
from backend.services.cache_service import get_vehicles_cached


class ValidationError(Exception):
    """Raised when fuel form input fails validation."""


def _require_float(value, field_name):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field_name} musi być liczbą.')


def _require_int(value, field_name):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field_name} musi być liczbą całkowitą.')


def register_routes(app):
    @app.route('/tankowania', methods=['GET', 'POST'], endpoint='fuel')
    @login_required
    def fuel():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicles = get_vehicles_cached()

            if request.method == 'POST':
                f = request.form
                try:
                    vehicle_id = f.get('vehicle_id', '').strip()
                    if not vehicle_id:
                        raise ValidationError('Wybierz pojazd.')

                    fuel_date = f.get('date', '').strip()
                    if not fuel_date:
                        raise ValidationError('Data jest wymagana.')

                    driver = f.get('driver', '').strip()
                    if not driver:
                        raise ValidationError('Kierowca jest wymagany.')

                    liters = _require_float(f.get('liters'), 'Litry')
                    if liters is None or liters <= 0:
                        raise ValidationError('Podaj poprawną ilość paliwa.')

                    cost = _require_float(f.get('cost'), 'Koszt')
                    odometer = _require_int(f.get('odometer'), 'Stan km')
                except ValidationError as exc:
                    flash(str(exc), 'error')
                    return redirect(url_for('fuel'))

                try:
                    cur.execute('''
                        INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        int(vehicle_id), fuel_date, driver,
                        odometer, liters, cost,
                        f.get('notes', '').strip(), session['username']
                    ))
                    conn.commit()
                except IntegrityError:
                    conn.rollback()
                    raise ValidationError('Nie udało się zapisać tankowania. Sprawdź dane i spróbuj ponownie.')

                flash('Tankowanie zapisane.', 'success')
                return redirect(url_for('fuel',
                                        vehicle_id=vehicle_id,
                                        okres=request.args.get('okres', ''),
                                        od=request.args.get('od', ''),
                                        do=request.args.get('do', ''),
                                        page=1))

            vid = request.args.get('vehicle_id', '')
            okres = request.args.get('okres', '')
            od = request.args.get('od', '')
            do_ = request.args.get('do', '')
            page = parse_positive_int(request.args.get('page'), default=1)

            where_parts = []
            params = []

            if vid:
                where_parts.append('f.vehicle_id = %s')
                params.append(vid)

            date_parts, date_params = build_date_where(okres, od, do_, alias='f')
            where_parts += date_parts
            params += date_params

            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

            base_sql = f'''
                SELECT f.*, v.name AS vname FROM fuel f
                JOIN vehicles v ON f.vehicle_id = v.id
                {where_sql}
                ORDER BY f.date DESC, f.created_at DESC
            '''
            count_sql = f'SELECT COUNT(*) AS count FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id {where_sql}'

            entries, total, total_pages, page = paginate(
                conn, cur, count_sql, params, base_sql, params, page
            )

            add_open = request.args.get('add', '') == '1'
        except ValidationError as exc:
            conn.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('fuel'))
        finally:
            cur.close()
        return render_template('fuel.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_vehicle=vid,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total,
                               add_open=add_open)
