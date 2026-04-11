from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate


class ValidationError(Exception):
    """Raised when trip form input fails validation."""


def _require_int(value, field_name):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field_name} musi być liczbą całkowitą.')


def register_routes(app):
    @app.route('/wyjazdy', methods=['GET', 'POST'], endpoint='trips')
    @login_required
    def trips():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
            vehicles = cur.fetchall()

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

                try:
                    cur.execute('''
                        INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        int(vehicle_id), trip_date, driver,
                        odo_start, odo_end,
                        purpose, f.get('notes', '').strip(),
                        session['username']
                    ))
                    conn.commit()
                except IntegrityError:
                    conn.rollback()
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
            page = int(request.args.get('page', 1))

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
