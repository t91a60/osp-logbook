from flask import render_template, request, flash, redirect, url_for, session, abort
from datetime import date, timedelta
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate, parse_positive_int, normalize_iso_date


class ValidationError(Exception):
    """Raised when maintenance form input fails validation."""


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
    @app.route('/serwis', methods=['GET', 'POST'], endpoint='maintenance')
    @login_required
    def maintenance():
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

                maintenance_date = f.get('date', '').strip()
                if not maintenance_date:
                    raise ValidationError('Data jest wymagana.')

                description = f.get('description', '').strip()
                if not description:
                    raise ValidationError('Opis jest wymagany.')

                priority = f.get('priority', 'medium')
                if priority not in ('low', 'medium', 'high'):
                    priority = 'medium'

                status = f.get('status', 'pending')
                if status not in ('pending', 'completed'):
                    status = 'pending'

                try:
                    odometer = _require_int(f.get('odometer'), 'Stan km')
                    cost = _require_float(f.get('cost'), 'Koszt')
                except ValidationError as exc:
                    flash(str(exc), 'error')
                    return redirect(url_for('maintenance'))

                try:
                    cur.execute('''
                        INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        int(vehicle_id), maintenance_date,
                        odometer,
                        description,
                        cost,
                        f.get('notes', '').strip(),
                        session['username'],
                        status, priority,
                        f.get('due_date') or None,
                    ))
                    conn.commit()
                except IntegrityError:
                    conn.rollback()
                    raise ValidationError('Nie udało się zapisać wpisu serwisowego. Sprawdź dane i spróbuj ponownie.')

                flash('Wpis serwisowy zapisany.', 'success')
                return redirect(url_for('maintenance',
                                        vehicle_id=request.args.get('vehicle_id', 'all'),
                                        status=request.args.get('status', 'all'),
                                        okres=request.args.get('okres', ''),
                                        od=request.args.get('od', ''),
                                        do=request.args.get('do', ''),
                                        page=1))

            selected_status = request.args.get('status', 'all')
            selected_vehicle = request.args.get('vehicle_id', 'all')
            okres = request.args.get('okres', '')
            od = request.args.get('od', '')
            do_ = request.args.get('do', '')
            page = parse_positive_int(request.args.get('page'), default=1)

            where_parts = []
            params_list = []

            if selected_vehicle != 'all':
                where_parts.append('m.vehicle_id = %s')
                params_list.append(selected_vehicle)

            if selected_status == 'pending':
                where_parts.append("(m.status = 'pending' AND (m.due_date IS NULL OR m.due_date >= CURRENT_DATE))")
            elif selected_status == 'completed':
                where_parts.append("m.status = 'completed'")
            elif selected_status == 'overdue':
                where_parts.append("(m.status = 'pending' AND m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE)")

            date_parts, date_params = build_date_where(okres, od, do_, alias='m')
            where_parts += date_parts
            params_list += date_params

            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

            base_sql = f'''
                SELECT m.*, v.name AS vname,
                       CASE
                           WHEN m.status = 'completed' THEN 'completed'
                           WHEN m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE THEN 'overdue'
                           ELSE 'pending'
                       END AS effective_status
                FROM maintenance m
                JOIN vehicles v ON m.vehicle_id = v.id
                {where_sql}
                ORDER BY m.date DESC, m.created_at DESC
            '''
            count_sql = f'SELECT COUNT(*) AS count FROM maintenance m JOIN vehicles v ON m.vehicle_id = v.id {where_sql}'

            entries, total, total_pages, page = paginate(
                conn, cur, count_sql, params_list, base_sql, params_list, page
            )
        except ValidationError as exc:
            conn.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('maintenance'))
        finally:
            cur.close()
        return render_template('maintenance.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_status=selected_status,
                               selected_vehicle=selected_vehicle,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total)

    @app.route('/serwis/<int:eid>/complete', methods=['POST'], endpoint='complete_maintenance')
    @login_required
    def complete_maintenance_view(eid):
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT added_by FROM maintenance WHERE id = %s', (eid,))
            row = cur.fetchone()
            if not row:
                flash('Nie znaleziono wpisu serwisowego.', 'error')
                return redirect(url_for('maintenance'))
            if row['added_by'] != session['username'] and not session.get('is_admin'):
                abort(403)
            cur.execute("UPDATE maintenance SET status = 'completed' WHERE id = %s", (eid,))
            conn.commit()
        finally:
            cur.close()
        flash('Oznaczono jako wykonane.', 'success')
        return redirect(url_for('maintenance'))

    @app.route('/serwis/<int:eid>/next', methods=['POST'], endpoint='create_next_maintenance')
    @login_required
    def create_next_maintenance_view(eid):
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('''
                SELECT vehicle_id, odometer, description, notes, priority, due_date
                FROM maintenance WHERE id = %s
            ''', (eid,))
            row = cur.fetchone()

            if not row:
                flash('Nie znaleziono wpisu serwisowego.', 'error')
                return redirect(url_for('maintenance'))

            cur.execute('SELECT added_by FROM maintenance WHERE id = %s', (eid,))
            owner_row = cur.fetchone()
            if owner_row and owner_row['added_by'] != session['username'] and not session.get('is_admin'):
                abort(403)

            if row['due_date']:
                normalized_due = normalize_iso_date(row['due_date'])
                if normalized_due is not None:
                    next_due = (date.fromisoformat(normalized_due) + timedelta(days=90)).isoformat()
                else:
                    next_due = (date.today() + timedelta(days=90)).isoformat()
            else:
                next_due = (date.today() + timedelta(days=90)).isoformat()

            cur.execute('''
                INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                row['vehicle_id'],
                date.today().isoformat(),
                row['odometer'],
                row['description'],
                None,
                row['notes'] or '',
                session['username'],
                'pending',
                row['priority'] or 'medium',
                next_due,
            ))
            conn.commit()
        finally:
            cur.close()
        flash('Dodano kolejny wpis serwisowy.', 'success')
        return redirect(url_for('maintenance'))
