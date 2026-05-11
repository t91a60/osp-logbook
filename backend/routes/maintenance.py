from flask import render_template, request, flash, redirect, url_for, session, abort
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
from backend.infrastructure.repositories.maintenance import MaintenanceRepository
from backend.infrastructure.repositories.vehicles import VehicleRepository
from backend.services.audit_service import AuditService


def register_routes(app):
    @app.route('/serwis', methods=['GET', 'POST'], endpoint='maintenance')
    @login_required
    def maintenance():
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
                maintenance_date = validate_iso_date(f.get('date'), 'Data')
                description = ensure_non_empty_text(f.get('description'), 'Opis')
            except ValueError as exc:
                raise ValidationError(str(exc))

            priority = f.get('priority', 'medium')
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'

            status = f.get('status', 'pending')
            if status not in ('pending', 'completed'):
                status = 'pending'

            odometer = require_int_field(f.get('odometer'), 'Stan km')
            cost = require_float_field(f.get('cost'), 'Koszt')

            try:
                MaintenanceRepository.add(
                    vehicle['id'],
                    maintenance_date,
                    odometer,
                    description,
                    cost,
                    f.get('notes', '').strip(),
                    session['username'],
                    status,
                    priority,
                    f.get('due_date') or None,
                )
                AuditService.log('Dodanie', 'Serwis', f'Pojazd ID: {vehicle_id}, Opis: {description}, Data: {maintenance_date}')
            except IntegrityError:
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
        return render_template('maintenance.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_status=selected_status,
                               selected_vehicle=selected_vehicle,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total)

    @app.route('/serwis/<int:eid>/edytuj', methods=['GET', 'POST'], endpoint='maintenance_edit')
    @login_required
    def maintenance_edit(eid):
        entry = MaintenanceRepository.get_by_id(eid)
        if not entry:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
            return redirect(url_for('maintenance'))

        # Only owner or admin may edit
        if entry.get('added_by') != session['username'] and not session.get('is_admin'):
            raise ForbiddenError('Brak uprawnień do edycji wpisu serwisowego.')

        vehicles = get_vehicles_cached()

        if request.method == 'POST':
            f = request.form
            vehicle_id = f.get('vehicle_id', '').strip()
            if not vehicle_id:
                raise ValidationError('Wybierz pojazd.')

            try:
                maintenance_date = validate_iso_date(f.get('date'), 'Data')
                description = ensure_non_empty_text(f.get('description'), 'Opis')
            except ValueError as exc:
                raise ValidationError(str(exc))

            priority = f.get('priority', 'medium')
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'

            status = f.get('status', 'pending')
            if status not in ('pending', 'completed'):
                status = 'pending'

            odometer = require_int_field(f.get('odometer'), 'Stan km')
            cost = require_float_field(f.get('cost'), 'Koszt')
            vehicle = VehicleRepository.get_active(vehicle_id)
            if not vehicle:
                raise ValidationError('Nieprawidłowy pojazd.')

            try:
                MaintenanceRepository.update(
                    eid,
                    vehicle['id'],
                    maintenance_date,
                    odometer,
                    description,
                    cost,
                    f.get('notes', '').strip(),
                    status,
                    priority,
                    f.get('due_date') or None,
                )
                AuditService.log('Edycja', 'Serwis', f'ID: {eid}, Pojazd: {vehicle_id}, Data: {maintenance_date}')
            except (NotFoundError, IntegrityError) as exc:
                raise ValidationError(str(exc))

            flash('Wpis serwisowy zaktualizowany.', 'success')
            return redirect(url_for('maintenance', vehicle_id=vehicle_id))

        return render_template(
            'maintenance_edit.html',
            entry=entry,
            vehicles=vehicles,
            today=date.today().isoformat(),
        )

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

    @app.route('/serwis/<int:eid>/usun', methods=['POST'], endpoint='maintenance_delete')
    @login_required
    def maintenance_delete(eid):
        try:
            MaintenanceRepository.delete(
                eid,
                requester=session['username'],
                is_admin=bool(session.get('is_admin')),
            )
            AuditService.log('Usunięcie', 'Serwis', f'ID: {eid}')
            flash('Wpis serwisowy usunięty.', 'success')
        except NotFoundError:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
        except ForbiddenError:
            flash('Brak uprawnień do usunięcia wpisu serwisowego.', 'error')
        return redirect(url_for('maintenance'))
