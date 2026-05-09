from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor  # backward-compatible patch targets for tests
from backend.helpers import (
    login_required,
    build_date_where,
    paginate,
    parse_positive_int,
    parse_trip_equipment_form,
    get_active_vehicle,
    validate_iso_date,
    ensure_non_empty_text,
    parse_positive_int_field,
    validate_odometer_range,
)
from backend.services.core_service import TripService
from backend.services.cache_service import get_vehicles_cached
from backend.helpers import ValidationError
from backend.infrastructure.repositories.trips import TripRepository


def _require_int(value, field_name):
    try:
        return parse_positive_int_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc))


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
                vehicle = get_active_vehicle(cur, vehicle_id)
                if not vehicle:
                    raise ValidationError('Nieprawidłowy pojazd.')

                trip_date = validate_iso_date(f.get('date'), 'Data')

                driver = ensure_non_empty_text(f.get('driver'), 'Kierowca')

                purpose_sel = f.get('purpose_select', '').strip()
                if purpose_sel == '__inne__':
                    purpose = ensure_non_empty_text(f.get('purpose_custom'), 'Cel wyjazdu')
                else:
                    purpose = ensure_non_empty_text(purpose_sel or f.get('purpose'), 'Cel wyjazdu')

                try:
                    odo_start = _require_int(f.get('odo_start'), 'Km start')
                    odo_end = _require_int(f.get('odo_end'), 'Km koniec')
                    validate_odometer_range(odo_start, odo_end)
                except (ValidationError, ValueError) as exc:
                    flash(str(exc), 'error')
                    return redirect(url_for('trips'))

                try:
                    equipment_used = parse_trip_equipment_form(request.form)
                except ValueError as exc:
                    raise ValidationError(str(exc))

                try:
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
            entries, total, total_pages, page = TripRepository.get_page(
                vehicle_id=vid,
                okres=okres,
                od=od,
                do_=do_,
                page=page,
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
