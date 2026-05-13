from __future__ import annotations

from datetime import date

from flask import abort, flash, redirect, render_template, request, session, url_for
from psycopg2 import IntegrityError

from backend.application import (
    AddMaintenanceCommand,
    AddMaintenanceUseCase,
    CompleteMaintenanceCommand,
    CompleteMaintenanceUseCase,
    CreateNextMaintenanceCommand,
    CreateNextMaintenanceUseCase,
    DeleteMaintenanceCommand,
    DeleteMaintenanceUseCase,
    EditMaintenanceCommand,
    EditMaintenanceUseCase,
    GetMaintenanceByIdUseCase,
    GetMaintenanceQuery,
    GetMaintenanceUseCase,
)
from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.helpers import login_required, parse_positive_int
from backend.services.cache_service import get_vehicles_cached


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

            cmd = AddMaintenanceCommand(
                vehicle_id=vehicle_id,
                date_val=f.get('date', ''),
                description=f.get('description', '').strip(),
                odometer=f.get('odometer') or None,
                cost=f.get('cost') or None,
                notes=f.get('notes', '').strip(),
                added_by=session['username'],
                status=f.get('status', 'pending'),
                priority=f.get('priority', 'medium'),
                due_date=f.get('due_date') or None,
            )
            try:
                AddMaintenanceUseCase.execute(cmd)
            except IntegrityError:
                raise ValidationError(
                    'Nie udało się zapisać wpisu serwisowego. Sprawdź dane i spróbuj ponownie.'
                )

            flash('Wpis serwisowy zapisany.', 'success')
            return redirect(url_for(
                'maintenance',
                vehicle_id=request.args.get('vehicle_id', 'all'),
                status=request.args.get('status', 'all'),
                okres=request.args.get('okres', ''),
                od=request.args.get('od', ''),
                do=request.args.get('do', ''),
                page=1,
            ))

        selected_status = request.args.get('status', 'all')
        selected_vehicle = request.args.get('vehicle_id', 'all')
        okres = request.args.get('okres', '')
        od = request.args.get('od', '')
        do_ = request.args.get('do', '')
        page = parse_positive_int(request.args.get('page'), default=1)

        query = GetMaintenanceQuery(
            vehicle_id=selected_vehicle,
            status_filter=selected_status,
            okres=okres,
            od=od,
            do_=do_,
            page=page,
        )
        entries, total, total_pages, page = GetMaintenanceUseCase.execute(query)

        return render_template(
            'maintenance.html',
            vehicles=vehicles,
            entries=entries,
            today=date.today().isoformat(),
            selected_status=selected_status,
            selected_vehicle=selected_vehicle,
            okres=okres, od=od, do_=do_,
            page=page, total_pages=total_pages, total=total,
        )

    @app.route('/serwis/<int:eid>/edytuj', methods=['GET', 'POST'], endpoint='maintenance_edit')
    @login_required
    def maintenance_edit(eid):
        entry = GetMaintenanceByIdUseCase.execute(eid)
        if not entry:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
            return redirect(url_for('maintenance'))

        # Ownership check before rendering the form
        if entry.get('added_by') != session['username'] and not session.get('is_admin'):
            raise ForbiddenError('Brak uprawnień do edycji wpisu serwisowego.')

        vehicles = get_vehicles_cached()

        if request.method == 'POST':
            f = request.form
            vehicle_id = f.get('vehicle_id', '').strip()
            if not vehicle_id:
                raise ValidationError('Wybierz pojazd.')

            cmd = EditMaintenanceCommand(
                entry_id=eid,
                vehicle_id=vehicle_id,
                date_val=f.get('date', ''),
                description=f.get('description', '').strip(),
                odometer=f.get('odometer') or None,
                cost=f.get('cost') or None,
                notes=f.get('notes', '').strip(),
                requester=session['username'],
                status=f.get('status', 'pending'),
                priority=f.get('priority', 'medium'),
                due_date=f.get('due_date') or None,
                is_admin=bool(session.get('is_admin')),
            )
            try:
                EditMaintenanceUseCase.execute(cmd)
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
        cmd = CompleteMaintenanceCommand(
            entry_id=eid,
            requester=session['username'],
            is_admin=bool(session.get('is_admin')),
        )
        try:
            CompleteMaintenanceUseCase.execute(cmd)
            flash('Oznaczono jako wykonane.', 'success')
        except NotFoundError:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
        except ForbiddenError:
            abort(403)
        return redirect(url_for('maintenance'))

    @app.route('/serwis/<int:eid>/next', methods=['POST'], endpoint='create_next_maintenance')
    @login_required
    def create_next_maintenance_view(eid):
        cmd = CreateNextMaintenanceCommand(
            entry_id=eid,
            added_by=session['username'],
            requester=session['username'],
            is_admin=bool(session.get('is_admin')),
        )
        try:
            CreateNextMaintenanceUseCase.execute(cmd)
            flash('Dodano kolejny wpis serwisowy.', 'success')
        except NotFoundError:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
        except ForbiddenError:
            abort(403)
        return redirect(url_for('maintenance'))

    @app.route('/serwis/<int:eid>/usun', methods=['POST'], endpoint='maintenance_delete')
    @login_required
    def maintenance_delete(eid):
        cmd = DeleteMaintenanceCommand(
            entry_id=eid,
            requester=session['username'],
            is_admin=bool(session.get('is_admin')),
        )
        try:
            DeleteMaintenanceUseCase.execute(cmd)
            flash('Wpis serwisowy usunięty.', 'success')
        except NotFoundError:
            flash('Nie znaleziono wpisu serwisowego.', 'error')
        except ForbiddenError:
            flash('Brak uprawnień do usunięcia wpisu serwisowego.', 'error')
        return redirect(url_for('maintenance'))
