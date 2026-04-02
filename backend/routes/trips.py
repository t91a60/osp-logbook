from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import date
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate

trips_bp = Blueprint('trips', __name__)

@trips_bp.route('/wyjazdy', methods=['GET', 'POST'], endpoint='trips')
@login_required
def trips():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
    vehicles = cur.fetchall()

    if request.method == 'POST':
        f = request.form
        purpose_sel = f.get('purpose_select', '').strip()
        if purpose_sel == '__inne__':
            purpose = f.get('purpose_custom', '').strip()
        else:
            purpose = purpose_sel or f.get('purpose', '').strip()

        try:
            odo_start = int(f.get('odo_start')) if f.get('odo_start') else None
            odo_end = int(f.get('odo_end')) if f.get('odo_end') else None
        except ValueError:
            flash('Błąd: Liczba kilometrów musi być liczbą całkowitą.', 'error')
            cur.close()
            return redirect(url_for('trips.trips'))

        cur.execute('''
            INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            odo_start, odo_end,
            purpose, f.get('notes', '').strip(),
            session['username']
        ))
        conn.commit()
        from backend.services.audit_service import AuditService
        AuditService.log('Dodanie', 'Wyjazd', f"Pojazd ID: {f['vehicle_id']}, Cel: {purpose}")
        flash('Wyjazd zapisany.', 'success')
        cur.close()
        return redirect(url_for('trips.trips',
                                vehicle_id=f.get('vehicle_id', ''),
                                okres=request.args.get('okres', ''),
                                od=request.args.get('od', ''),
                                do=request.args.get('do', ''),
                                page=1))

    vid = request.args.get('vehicle_id', '')
    okres = request.args.get('okres', '')
    od = request.args.get('od', '')
    do_ = request.args.get('do', '')
    page = int(request.args.get('page', 1))

    where_parts = []
    params = []

    if vid:
        where_parts.append('t.vehicle_id = %s')
        params.append(vid)

    date_parts, date_params = build_date_where(okres, od, do_, alias='t')
    where_parts += date_parts
    params += date_params

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

    base_sql = f'''
        SELECT t.*, v.name AS vname FROM trips t
        JOIN vehicles v ON t.vehicle_id = v.id
        {where_sql}
        ORDER BY t.date DESC, t.created_at DESC
    '''
    count_sql = f'SELECT COUNT(*) AS count FROM trips t JOIN vehicles v ON t.vehicle_id = v.id {where_sql}'

    entries, total, total_pages, page = paginate(
        conn, cur, count_sql, params, base_sql, params, page
    )

    add_open = request.args.get('add', '') == '1'
    cur.close()

    return render_template('trips.html',
                           vehicles=vehicles,
                           entries=entries,
                           today=date.today().isoformat(),
                           selected_vehicle=vid,
                           okres=okres, od=od, do_=do_,
                           page=page, total_pages=total_pages, total=total,
                           add_open=add_open)