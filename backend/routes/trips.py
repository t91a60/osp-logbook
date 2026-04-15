from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate, parse_positive_int
from backend.services.core_service import TripService
from backend.services.cache_service import get_vehicles_cached


class ValidationError(Exception):
    """Raised when trip form input fails validation."""


def _require_int(value, field_name):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field_name} musi być liczbą całkowitą.')


def _parse_trip_equipment(form) -> list[dict]:
    eq_ids = form.getlist('eq_id[]')
    eq_qtys = form.getlist('eq_qty[]')
    eq_mins = form.getlist('eq_min[]')
    max_len = max(len(eq_ids), len(eq_qtys), len(eq_mins), 0)

    equipment_used = []
    for i in range(max_len):
        eq_id_raw = (eq_ids[i] if i < len(eq_ids) else '').strip()
        eq_qty_raw = (eq_qtys[i] if i < len(eq_qtys) else '').strip()
        eq_min_raw = (eq_mins[i] if i < len(eq_mins) else '').strip()

        if not (eq_id_raw or eq_qty_raw or eq_min_raw):
            continue

        try:
            eq_id = int(eq_id_raw)
        except (TypeError, ValueError):
            raise ValidationError('Wybierz poprawny sprzęt.')
        if eq_id <= 0:
            raise ValidationError('Wybierz poprawny sprzęt.')

        if not eq_min_raw:
            raise ValidationError('Podaj czas użycia sprzętu (minuty).')
        try:
            eq_min = int(eq_min_raw)
        except (TypeError, ValueError):
            raise ValidationError('Czas użycia sprzętu musi być liczbą całkowitą.')
        if eq_min <= 0:
            raise ValidationError('Czas użycia sprzętu musi być większy od 0.')

        eq_qty = 1
        if eq_qty_raw:
            try:
                eq_qty = int(eq_qty_raw)
            except (TypeError, ValueError):
                raise ValidationError('Ilość sprzętu musi być liczbą całkowitą.')
            if eq_qty <= 0:
                raise ValidationError('Ilość sprzętu musi być większa od 0.')

        equipment_used.append({
            'equipment_id': eq_id,
            'quantity_used': eq_qty,
            'minutes_used': eq_min,
        })

    return equipment_used


def register_routes(app):
    @app.route('/wyjazdy', methods=['GET', 'POST'], endpoint='trips')
    @login_required
    def trips():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicles = get_vehicles_cached()

            if request.method == 'POST':
                f = request.form
                vehicle_id = f.get('vehicle_id', '').strip()
                if not vehicle_id:
                    raise ValidationError('Wybierz pojazd.')

                trip_date = f.get('date', '').strip()
                if not trip_date:
                    raise ValidationError('Data jest wymagana.')

                driver = f.get('driver', '').strip()
                if not driver:
                    raise ValidationError('Kierowca jest wymagany.')

                purpose_sel = f.get('purpose_select', '').strip()
                if purpose_sel == '__inne__':
                    purpose = f.get('purpose_custom', '').strip()
                else:
                    purpose = purpose_sel or f.get('purpose', '').strip()

                if not purpose:
                    raise ValidationError('Cel wyjazdu jest wymagany.')

                try:
                    odo_start = _require_int(f.get('odo_start'), 'Km start')
                    odo_end = _require_int(f.get('odo_end'), 'Km koniec')
                except ValidationError as exc:
                    flash(str(exc), 'error')
                    return redirect(url_for('trips'))

                equipment_used = _parse_trip_equipment(request.form)

                try:
                    TripService.add_trip(
                        int(vehicle_id),
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
                except IntegrityError:
                    raise ValidationError('Nie udało się zapisać wyjazdu. Sprawdź dane i spróbuj ponownie.')

                flash('Wyjazd zapisany.', 'success')
                return redirect(url_for('trips',
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
                where_parts.append('t.vehicle_id = %s')
                params.append(vid)

            date_parts, date_params = build_date_where(okres, od, do_, alias='t')
            where_parts += date_parts
            params += date_params

            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

            base_sql = f'''
                SELECT t.*, v.name AS vname FROM trips t
                JOIN vehicles v ON t.vehicle_id = v.id
                {where_sql}
                ORDER BY t.date DESC, t.created_at DESC
            '''
            count_sql = f'SELECT COUNT(*) AS count FROM trips t JOIN vehicles v ON t.vehicle_id = v.id {where_sql}'

            entries, total, total_pages, page = paginate(
                conn, cur, count_sql, params, base_sql, params, page
            )

            add_open = request.args.get('add', '') == '1'
        except ValidationError as exc:
            conn.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('trips'))
        finally:
            cur.close()
        return render_template('trips.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_vehicle=vid,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total,
                               add_open=add_open)
