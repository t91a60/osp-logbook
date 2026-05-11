from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.helpers import (
    login_required,
    parse_positive_int,
    parse_trip_equipment_form,
    validate_iso_date,
    ensure_non_empty_text,
    parse_positive_int_field,
    validate_odometer_range,
)
from backend.services.cache_service import get_vehicles_cached
from backend.domain.exceptions import ValidationError
from backend.infrastructure.repositories.trips import TripRepository
from backend.infrastructure.repositories.vehicles import VehicleRepository
from backend.services.audit_service import AuditService
from backend.services.core_service import TripService


def register_routes(app):
    @app.route('/wyjazdy', methods=['GET', 'POST'], endpoint='trips')
    @login_required
    def trips():
        vehicles = get_vehicles_cached()

        if request.method == 'POST':
            f = request.form
            vehicle_id = f.get('vehicle_id', '').strip()
            if not vehicle_id:
                raise ValidationError('Wybierz pojazd.')
            vehicle = VehicleRepository.get_active(vehicle_id)
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

            try:
                trip_date = validate_iso_date(f.get('date'), 'Data')
                driver = ensure_non_empty_text(f.get('driver'), 'Kierowca')
            except ValueError as exc:
                raise ValidationError(str(exc))

            purpose_sel = f.get('purpose_select', '').strip()
            if purpose_sel == '__inne__':
                try:
                    purpose = ensure_non_empty_text(f.get('purpose_custom'), 'Cel wyjazdu')
                except ValueError as exc:
                    raise ValidationError(str(exc))
            else:
                try:
                    purpose = ensure_non_empty_text(purpose_sel or f.get('purpose'), 'Cel wyjazdu')
                except ValueError as exc:
                    raise ValidationError(str(exc))

            try:
                odo_start = parse_positive_int_field(f.get('odo_start'), 'Km start')
                odo_end = parse_positive_int_field(f.get('odo_end'), 'Km koniec')
                validate_odometer_range(odo_start, odo_end)
            except ValueError as exc:
                raise ValidationError(str(exc))

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
        return render_template('trips.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_vehicle=vid,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total,
                               add_open=add_open)
