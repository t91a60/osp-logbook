from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.helpers import (
    login_required,
    parse_positive_int,
    validate_iso_date,
    ensure_non_empty_text,
    parse_positive_float_field,
    parse_positive_int_field,
)
from backend.services.cache_service import get_vehicles_cached
from backend.domain.exceptions import ValidationError
from backend.infrastructure.repositories.fuel import FuelRepository
from backend.infrastructure.repositories.vehicles import VehicleRepository
from backend.services.audit_service import AuditService


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
    @app.route('/tankowania', methods=['GET', 'POST'], endpoint='fuel')
    @login_required
    def fuel():
        vehicles = get_vehicles_cached()

        if request.method == 'POST':
            f = request.form
            vehicle_id = f.get('vehicle_id', '').strip()
            if not vehicle_id:
                raise ValidationError('Wybierz pojazd.')

            try:
                fuel_date = validate_iso_date(f.get('date'), 'Data')
                driver = ensure_non_empty_text(f.get('driver'), 'Kierowca')
            except ValueError as exc:
                raise ValidationError(str(exc))

            liters = _require_float(f.get('liters'), 'Litry')
            if liters is None:
                raise ValidationError('Podaj ilość paliwa.')

            cost = _require_float(f.get('cost'), 'Koszt')
            odometer = _require_int(f.get('odometer'), 'Stan km')
            vehicle = VehicleRepository.get_active(vehicle_id)
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

            try:
                FuelRepository.add(
                    vehicle['id'],
                    fuel_date,
                    driver,
                    odometer,
                    liters,
                    cost,
                    f.get('notes', '').strip(),
                    session['username'],
                )
                AuditService.log('Dodanie', 'Tankowanie', f'Pojazd ID: {vehicle_id}, Litry: {liters}, Data: {fuel_date}')
            except IntegrityError:
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
        entries, total, total_pages, page = FuelRepository.get_page(
            vehicle_id=vid,
            okres=okres,
            od=od,
            do_=do_,
            page=page,
        )

        add_open = request.args.get('add', '') == '1'
        return render_template('fuel.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_vehicle=vid,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total,
                               add_open=add_open)
