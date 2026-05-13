from __future__ import annotations

from datetime import date

from flask import flash, redirect, render_template, request, session, url_for
from psycopg2 import IntegrityError

from backend.application import (
    AddFuelCommand,
    AddFuelUseCase,
    DeleteFuelCommand,
    DeleteFuelUseCase,
    EditFuelCommand,
    EditFuelUseCase,
    GetFuelByIdUseCase,
    GetFuelQuery,
    GetFuelUseCase,
)
from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.helpers import login_required, parse_positive_int
from backend.services.cache_service import get_vehicles_cached


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

            cmd = AddFuelCommand(
                vehicle_id=vehicle_id,
                date_val=f.get('date', ''),
                driver=f.get('driver', '').strip(),
                odometer=f.get('odometer') or None,
                liters=f.get('liters') or None,
                cost=f.get('cost') or None,
                notes=f.get('notes', '').strip(),
                added_by=session['username'],
            )
            try:
                AddFuelUseCase.execute(cmd)
            except IntegrityError:
                raise ValidationError(
                    'Nie udało się zapisać tankowania. Sprawdź dane i spróbuj ponownie.'
                )

            flash('Tankowanie zapisane.', 'success')
            return redirect(url_for(
                'fuel',
                vehicle_id=vehicle_id,
                okres=request.args.get('okres', ''),
                od=request.args.get('od', ''),
                do=request.args.get('do', ''),
                page=1,
            ))

        vid = request.args.get('vehicle_id', '')
        okres = request.args.get('okres', '')
        od = request.args.get('od', '')
        do_ = request.args.get('do', '')
        page = parse_positive_int(request.args.get('page'), default=1)

        query = GetFuelQuery(
            vehicle_id=vid,
            okres=okres,
            od=od,
            do_=do_,
            page=page,
        )
        entries, total, total_pages, page = GetFuelUseCase.execute(query)

        add_open = request.args.get('add', '') == '1'
        return render_template(
            'fuel.html',
            vehicles=vehicles,
            entries=entries,
            today=date.today().isoformat(),
            selected_vehicle=vid,
            okres=okres, od=od, do_=do_,
            page=page, total_pages=total_pages, total=total,
            add_open=add_open,
        )

    @app.route('/tankowania/<int:eid>/edytuj', methods=['GET', 'POST'], endpoint='fuel_edit')
    @login_required
    def fuel_edit(eid):
        entry = GetFuelByIdUseCase.execute(eid)
        if not entry:
            flash('Nie znaleziono wpisu tankowania.', 'error')
            return redirect(url_for('fuel'))

        # Ownership check before even rendering the form
        if entry.get('added_by') != session['username'] and not session.get('is_admin'):
            raise ForbiddenError('Brak uprawnień do edycji wpisu tankowania.')

        vehicles = get_vehicles_cached()

        if request.method == 'POST':
            f = request.form
            vehicle_id = f.get('vehicle_id', '').strip()
            if not vehicle_id:
                raise ValidationError('Wybierz pojazd.')

            cmd = EditFuelCommand(
                entry_id=eid,
                vehicle_id=vehicle_id,
                date_val=f.get('date', ''),
                driver=f.get('driver', '').strip(),
                odometer=f.get('odometer') or None,
                liters=f.get('liters') or None,
                cost=f.get('cost') or None,
                notes=f.get('notes', '').strip(),
                requester=session['username'],
                is_admin=bool(session.get('is_admin')),
            )
            try:
                EditFuelUseCase.execute(cmd)
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
        cmd = DeleteFuelCommand(
            entry_id=eid,
            requester=session['username'],
            is_admin=bool(session.get('is_admin')),
        )
        try:
            DeleteFuelUseCase.execute(cmd)
            flash('Wpis tankowania usunięty.', 'success')
        except NotFoundError:
            flash('Nie znaleziono wpisu tankowania.', 'error')
        except ForbiddenError:
            flash('Brak uprawnień do usunięcia wpisu tankowania.', 'error')
        return redirect(url_for('fuel'))
