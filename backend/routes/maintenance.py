from flask import render_template, request, flash, redirect, url_for, session, abort
from datetime import date
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import (
    login_required,
    parse_positive_int,
    get_active_vehicle,
    validate_iso_date,
    ensure_non_empty_text,
    parse_positive_float_field,
    parse_positive_int_field,
)
from backend.services.cache_service import get_vehicles_cached
from backend.helpers import ValidationError
from backend.infrastructure.repositories.maintenance import MaintenanceRepository


def _require_float(value, field_name):
    try:
        return parse_positive_float_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc))


def _require_int(value, field_name):
    try:
        return parse_positive_int_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc))


def register_routes(app):
    @app.route('/serwis', methods=['GET', 'POST'], endpoint='maintenance')
    @login_required
    def maintenance():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            vehicles = get_vehicles_cached()

            if request.method == 'POST':
                f = request.form
                vehicle_id = f.get('vehicle_id', '').strip()
                if not vehicle_id:
                    raise ValidationError('Wybierz pojazd.')
                vehicle = get_active_vehicle(cur, vehicle_id)
                if not vehicle:
                    raise ValidationError('Nieprawidłowy pojazd.')

                maintenance_date = validate_iso_date(f.get('date'), 'Data')

                description = ensure_non_empty_text(f.get('description'), 'Opis')

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
            entries, total, total_pages, page = MaintenanceRepository.get_page(
                vehicle_id=selected_vehicle,
                status_filter=selected_status,
                okres=okres,
                od=od,
                do_=do_,
                page=page,
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
        row = MaintenanceRepository.complete(eid)
        if not row:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
            return redirect(url_for('maintenance'))
        if row['added_by'] != session['username'] and not session.get('is_admin'):
            abort(403)
        flash('Oznaczono jako wykonane.', 'success')
        return redirect(url_for('maintenance'))

    @app.route('/serwis/<int:eid>/next', methods=['POST'], endpoint='create_next_maintenance')
    @login_required
    def create_next_maintenance_view(eid):
        row = MaintenanceRepository.create_next(eid, added_by=session['username'])
        if not row:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
            return redirect(url_for('maintenance'))
        if row['added_by'] != session['username'] and not session.get('is_admin'):
            abort(403)
        flash('Dodano kolejny wpis serwisowy.', 'success')
        return redirect(url_for('maintenance'))
