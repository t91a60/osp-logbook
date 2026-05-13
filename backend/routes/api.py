from __future__ import annotations

from datetime import date

from flask import Response, current_app, jsonify, request, session

from backend.application import (
    AddFuelCommand,
    AddFuelUseCase,
    AddMaintenanceCommand,
    AddMaintenanceUseCase,
    AddTripCommand,
    AddTripUseCase,
    UseCaseFactory,
)
from backend.domain.exceptions import DomainError, ValidationError
from backend.helpers import (
    login_required,
    normalize_iso_date,
    parse_trip_equipment_form,
)
from backend.services.cache_service import get_or_set


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({'success': False, 'message': message}), status_code


def register_routes(app):
    from app import limiter

    # ── Read-only API: last odometer reading ──────────────────────────────

    @app.route('/api/vehicle/<int:vid>/last_km', endpoint='api_vehicle_last_km')
    @login_required
    @limiter.limit('120 per minute')
    def api_vehicle_last_km(vid):
        cache_key = f'api:last_km:{vid}'
        vehicle_repo = UseCaseFactory.get_vehicle_repo()
        km, dt = get_or_set(
            cache_key,
            ttl_seconds=30,
            loader=lambda: vehicle_repo.get_last_km(vid),
        )

        days_ago = None
        if dt:
            try:
                days_ago = (date.today() - date.fromisoformat(normalize_iso_date(dt))).days
            except (TypeError, ValueError):
                pass

        return jsonify({'km': km, 'date': dt, 'days_ago': days_ago})

    # ── Read-only API: recent drivers ─────────────────────────────────────

    @app.route('/api/drivers', endpoint='api_drivers')
    @login_required
    @limiter.limit('120 per minute')
    def api_drivers():
        vehicle_repo = UseCaseFactory.get_vehicle_repo()
        drivers = get_or_set(
            'api:drivers:90d',
            ttl_seconds=300,
            loader=lambda: vehicle_repo.get_recent_drivers(days=90),
        )
        return jsonify(drivers)

    # ── Write API: add trip ───────────────────────────────────────────────

    @app.route('/api/trips', methods=['POST'], endpoint='api_add_trip')
    @login_required
    @limiter.limit('60 per minute')
    def api_add_trip():
        f = request.form

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
            vehicle_id=f.get('vehicle_id', ''),
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
        except DomainError:
            raise
        except Exception:
            current_app.logger.exception('Trip API error')
            return _json_error('Nie udało się zapisać wyjazdu. Spróbuj ponownie.', 500)

        return jsonify({'success': True, 'message': '✓ Wyjazd zapisany'})

    # ── Write API: add fuel ───────────────────────────────────────────────

    @app.route('/api/fuel', methods=['POST'], endpoint='api_add_fuel')
    @login_required
    @limiter.limit('60 per minute')
    def api_add_fuel():
        f = request.form

        cmd = AddFuelCommand(
            vehicle_id=f.get('vehicle_id', ''),
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
        except DomainError:
            raise
        except Exception:
            current_app.logger.exception('Fuel API error')
            return _json_error('Nie udało się zapisać tankowania. Spróbuj ponownie.', 500)

        return jsonify({'success': True, 'message': '✓ Tankowanie zapisane'})

    # ── Write API: add maintenance ────────────────────────────────────────

    @app.route('/api/maintenance', methods=['POST'], endpoint='api_add_maintenance')
    @login_required
    @limiter.limit('60 per minute')
    def api_add_maintenance():
        f = request.form

        cmd = AddMaintenanceCommand(
            vehicle_id=f.get('vehicle_id', ''),
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
        except DomainError:
            raise
        except Exception:
            current_app.logger.exception('Maintenance API error')
            return _json_error('Nie udało się zapisać wpisu. Spróbuj ponownie.', 500)

        return jsonify({'success': True, 'message': '✓ Wpis serwisowy zapisany'})
