from flask import render_template, request, flash, redirect, url_for, session
from datetime import date
from psycopg2 import IntegrityError
from backend.helpers import (
    login_required,
    parse_positive_int,
    validate_iso_date,
    ensure_non_empty_text,
    require_float_field,
    require_int_field,
)
from backend.services.cache_service import get_vehicles_cached
from backend.domain.exceptions import ValidationError, NotFoundError, ForbiddenError
from backend.infrastructure.repositories.fuel import FuelRepository
from backend.infrastructure.repositories.vehicles import VehicleRepository
from backend.services.audit_service import AuditService


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

            liters = require_float_field(f.get('liters'), 'Litry')
            if liters is None:
                raise ValidationError('Podaj ilość paliwa.')

            cost = require_float_field(f.get('cost'), 'Koszt')
            odometer = require_int_field(f.get('odometer'), 'Stan km')
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

    @app.route('/tankowania/<int:eid>/edytuj', methods=['GET', 'POST'], endpoint='fuel_edit')
    @login_required
    def fuel_edit(eid):
        entry = FuelRepository.get_by_id(eid)
        if not entry:
            flash('Nie znaleziono wpisu tankowania.', 'error')
            return redirect(url_for('fuel'))

        # Only owner or admin may edit
        if entry.get('added_by') != session['username'] and not session.get('is_admin'):
            raise ForbiddenError('Brak uprawnień do edycji wpisu tankowania.')

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

            liters = require_float_field(f.get('liters'), 'Litry')
            if liters is None:
                raise ValidationError('Podaj ilość paliwa.')

            cost = require_float_field(f.get('cost'), 'Koszt')
            odometer = require_int_field(f.get('odometer'), 'Stan km')
            vehicle = VehicleRepository.get_active(vehicle_id)
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

            try:
                FuelRepository.update(
                    eid,
                    vehicle['id'],
                    fuel_date,
                    driver,
                    odometer,
                    liters,
                    cost,
                    f.get('notes', '').strip(),
                )
                AuditService.log('Edycja', 'Tankowanie', f'ID: {eid}, Pojazd: {vehicle_id}, Data: {fuel_date}')
            except (NotFoundError, IntegrityError) as exc:
                raise ValidationError(str(exc))

            flash('Wpis tankowania zaktualizowany.', 'success')
            return redirect(url_for('fuel', vehicle_id=vehicle_id))

        return render_template(
            'fuel_edit.html',
            entry=entry,
            vehicles=vehicles,
            today=date.today().isoformat(),
        )

    @app.route('/tankowania/<int:eid>/usun', methods=['POST'], endpoint='fuel_delete')
    @login_required
    def fuel_delete(eid):
        try:
            FuelRepository.delete(
                eid,
                requester=session['username'],
                is_admin=bool(session.get('is_admin')),
            )
            AuditService.log('Usunięcie', 'Tankowanie', f'ID: {eid}')
            flash('Wpis tankowania usunięty.', 'success')
        except NotFoundError:
            flash('Nie znaleziono wpisu tankowania.', 'error')
        except ForbiddenError:
            flash('Brak uprawnień do usunięcia wpisu tankowania.', 'error')
        return redirect(url_for('fuel'))
