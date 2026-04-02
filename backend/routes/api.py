from flask import Blueprint, request, jsonify, session, current_app
from backend.helpers import login_required, days_since_iso_date
from backend.services.core_service import VehicleService, TripService

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/vehicle/<int:vid>/last_km', endpoint='api_vehicle_last_km')
@login_required
def api_vehicle_last_km(vid):
    km, dt = VehicleService.get_last_km(vid)
    days_ago = days_since_iso_date(dt)
    return jsonify({'km': km, 'date': dt, 'days_ago': days_ago})

@api_bp.route('/api/drivers', endpoint='api_drivers')
@login_required
def api_drivers():
    drivers = VehicleService.get_recent_drivers(90)
    return jsonify(drivers)

@api_bp.route('/api/trips', methods=['POST'], endpoint='api_add_trip')
@login_required
def api_add_trip():
    try:
        f = request.form
        purpose_sel = f.get('purpose_select', '').strip()
        purpose = f.get('purpose_custom', '').strip() if purpose_sel == '__inne__' else (purpose_sel or f.get('purpose', '').strip())
        
        TripService.add_trip(
            vehicle_id=f['vehicle_id'], date_val=f['date'], driver=f['driver'].strip(),
            odo_start=f.get('odo_start') or None, odo_end=f.get('odo_end') or None,
            purpose=purpose, notes=f.get('notes', '').strip(), added_by=session['username']
        )
        return jsonify({'success': True, 'message': '✓ Wyjazd zapisany'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd: {str(e)}'}), 400

@api_bp.route('/api/fuel', methods=['POST'], endpoint='api_add_fuel')
@login_required
def api_add_fuel():
    try:
        f = request.form
        liters = (f.get('liters') or '').strip()
        if not liters:
            return jsonify({'success': False, 'message': 'Podaj ilość paliwa.'}), 400
        
        TripService.add_fuel(
            vehicle_id=f['vehicle_id'], date_val=f['date'], driver=f['driver'].strip(),
            odometer=f.get('odometer') or None, liters=liters, cost=f.get('cost') or None,
            notes=f.get('notes', '').strip(), added_by=session['username']
        )
        return jsonify({'success': True, 'message': '✓ Tankowanie zapisane'})
    except Exception as e:
        current_app.logger.exception('Fuel API error: %s', e)
        return jsonify({'success': False, 'message': 'Nie udało się zapisać tankowania. Spróbuj ponownie.'}), 400

@api_bp.route('/api/maintenance', methods=['POST'], endpoint='api_add_maintenance')
@login_required
def api_add_maintenance():
    try:
        f = request.form
        priority = f.get('priority', 'medium')
        status = f.get('status', 'pending')
        
        TripService.add_maintenance(
            vehicle_id=f['vehicle_id'], date_val=f['date'], odometer=f.get('odometer') or None,
            description=f['description'].strip(), cost=f.get('cost') or None, 
            notes=f.get('notes', '').strip(), added_by=session['username'], 
            status=status if status in ('pending', 'completed') else 'pending',
            priority=priority if priority in ('low', 'medium', 'high') else 'medium',
            due_date=f.get('due_date') or None
        )
        return jsonify({'success': True, 'message': '✓ Wpis serwisowy zapisany'})
    except Exception as e:
        current_app.logger.exception('Maintenance API error: %s', e)
        return jsonify({'success': False, 'message': 'Nie udało się zapisać wpisu.'}), 400
