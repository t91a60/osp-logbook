from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import date
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate

fuel_bp = Blueprint('fuel', __name__)

@fuel_bp.route('/tankowania', methods=['GET', 'POST'], endpoint='fuel')
@login_required
def fuel():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
    vehicles = cur.fetchall()

    if request.method == 'POST':
        f = request.form
        
        try:
            liters = float(f.get('liters', 0))
            cost = float(f.get('cost')) if f.get('cost') else None
            odometer = int(f.get('odometer')) if f.get('odometer') else None
        except ValueError:
            flash('Błąd: Nieprawidłowy format danych liczbowych.', 'error')
            cur.close()
            return redirect(url_for('fuel.fuel'))

        cur.execute('''
            INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            odometer, liters, cost,
            f.get('notes', '').strip(), session['username']
        ))
        conn.commit()
        flash('Tankowanie zapisane.', 'success')
        cur.close()
        return redirect(url_for('fuel.fuel',
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
        where_parts.append('f.vehicle_id = %s')
        params.append(vid)

    date_parts, date_params = build_date_where(okres, od, do_, alias='f')
    where_parts += date_parts
    params += date_params

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

    base_sql = f'''
        SELECT f.*, v.name AS vname FROM fuel f
        JOIN vehicles v ON f.vehicle_id = v.id
        {where_sql}
        ORDER BY f.date DESC, f.created_at DESC
    '''
    count_sql = f'SELECT COUNT(*) AS count FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id {where_sql}'

    entries, total, total_pages, page = paginate(
        conn, cur, count_sql, params, base_sql, params, page
    )

    add_open = request.args.get('add', '') == '1'
    cur.close()

    return render_template('fuel.html',
                           vehicles=vehicles,
                           entries=entries,
                           today=date.today().isoformat(),
                           selected_vehicle=vid,
                           okres=okres, od=od, do_=do_,
                           page=page, total_pages=total_pages, total=total,
                           add_open=add_open)