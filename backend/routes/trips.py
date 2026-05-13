from __future__ import annotations

from datetime import date

from flask import flash, redirect, render_template, request, session, url_for
from psycopg2 import IntegrityError

from backend.application import (
    AddTripCommand,
    AddTripUseCase,
    GetTripsQuery,
    GetTripsUseCase,
)
from backend.domain.exceptions import ValidationError
from backend.helpers import (
    login_required,
    parse_positive_int,
    parse_trip_equipment_form,
)
from backend.services.cache_service import get_vehicles_cached


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

            # Resolve purpose — UI-specific select + custom field logic
            purpose_sel = f.get('purpose_select', '').strip()
            if purpose_sel == '__inne__':
                purpose = f.get('purpose_custom', '').strip()
            else:
                purpose = purpose_sel or f.get('purpose', '')

            try:
                equipment_used = parse_trip_equipment_form(request.form)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

            cmd = AddTripCommand(
                vehicle_id=vehicle_id,
                date_val=f.get('date', ''),
                driver=f.get('driver', '').strip(),
                odo_start=f.get('odo_start') or None,
                odo_end=f.get('odo_end') or None,
                purpose=purpose,
                notes=f.get('notes', '').strip(),
                added_by=session['username'],
                time_start=f.get('time_start') or None,
                time_end=f.get('time_end') or None,
                equipment_used=equipment_used or None,
            )
            try:
                AddTripUseCase.execute(cmd)
            except IntegrityError:
                raise ValidationError(
                    'Nie udało się zapisać wyjazdu. Sprawdź dane i spróbuj ponownie.'
                )

            flash('Wyjazd zapisany.', 'success')
            return redirect(url_for(
                'trips',
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

        query = GetTripsQuery(
            vehicle_id=vid,
            okres=okres,
            od=od,
            do_=do_,
            page=page,
        )
        entries, total, total_pages, page = GetTripsUseCase.execute(query)

        add_open = request.args.get('add', '') == '1'
        return render_template(
            'trips.html',
            vehicles=vehicles,
            entries=entries,
            today=date.today().isoformat(),
            selected_vehicle=vid,
            okres=okres, od=od, do_=do_,
            page=page, total_pages=total_pages, total=total,
            add_open=add_open,
        )
