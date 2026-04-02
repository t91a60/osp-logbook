from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from werkzeug.security import generate_password_hash
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required
from backend.services.audit_service import AuditService
from backend.services.vehicle_service import VehicleService

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/pojazdy', methods=['GET', 'POST'], endpoint='vehicles')
@login_required
def vehicles():
    conn = get_db()
    cur = get_cursor(conn)
    if request.method == 'POST':
        f = request.form
        cur.execute(
            'INSERT INTO vehicles (name, plate, type) VALUES (%s, %s, %s)',
            (f['name'].strip(), f.get('plate', '').strip(), f.get('type', '').strip())
        )
        conn.commit()
        AuditService.log('Dodanie', 'Pojazd', f"Nazwa: {f['name'].strip()}")
        flash('Pojazd dodany.', 'success')
        cur.close()
        return redirect(url_for('admin.vehicles'))

    cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
    vlist = cur.fetchall()
    cur.close()
    return render_template('vehicles.html', vehicles=vlist)



@admin_bp.route('/vehicles/<int:vid>/delete', methods=['POST'], endpoint='delete_vehicle')
@login_required
def delete_vehicle_view(vid):
    VehicleService.delete_vehicle(vid, session.get('user_id'))
    flash('Pojazd usunięty.', 'success')
    return redirect(url_for('admin.vehicles'))

@admin_bp.route('/uzytkownicy', methods=['GET', 'POST'], endpoint='users')
@login_required
def users():
    conn = get_db()
    cur = get_cursor(conn)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            pw = request.form.get('password', '')
            if len(pw) < 4:
                flash('Hasło musi mieć co najmniej 4 znaki.', 'error')
            else:
                try:
                    cur.execute(
                        'INSERT INTO users (username, password, display_name) VALUES (%s, %s, %s)',
                        (request.form['username'].strip(),
                         generate_password_hash(pw),
                         request.form['display_name'].strip())
                    )
                    conn.commit()
                    AuditService.log('Dodanie', 'Użytkownik', f"Dodano użytkownika: {request.form['username'].strip()}")
                    flash('Użytkownik dodany.', 'success')
                except IntegrityError:
                    conn.rollback()
                    flash('Login już istnieje.', 'error')
        elif action == 'change_pw':
            uid = request.form.get('uid')
            new_pw = request.form.get('new_password', '')
            if uid and len(new_pw) >= 4:
                cur.execute('UPDATE users SET password = %s WHERE id = %s',
                             (generate_password_hash(new_pw), uid))
                conn.commit()
                AuditService.log('Edycja', 'Użytkownik', f"Zmieniono hasło dla UID: {uid}")
                flash('Hasło zmienione.', 'success')
            else:
                flash('Hasło musi mieć co najmniej 4 znaki.', 'error')
        elif action == 'delete':
            uid = request.form.get('uid')
            if uid:
                if str(session.get('user_id')) == str(uid):
                    flash('Nie możesz usunąć samego siebie.', 'error')
                else:
                    try:
                        cur.execute('DELETE FROM users WHERE id = %s', (uid,))
                        conn.commit()
                        AuditService.log('Usunięcie', 'Użytkownik', f"Usunięto użytkownika UID: {uid}")
                        flash('Użytkownik został usunięty.', 'success')
                    except IntegrityError:
                        conn.rollback()
                        flash('Nie można usunąć użytkownika, ponieważ posiada on przypisane statystyki lub wyjazdy.', 'error')
        cur.close()
        return redirect(url_for('admin.users'))

    cur.execute('SELECT id, username, display_name FROM users ORDER BY display_name')
    all_users = cur.fetchall()
    cur.close()
    return render_template('users.html', users=all_users)

@admin_bp.route('/usun/<string:kind>/<int:eid>', methods=['POST'], endpoint='delete_entry')
@login_required
def delete_entry_view(kind, eid):
    tables = {'wyjazd': 'trips', 'tankowanie': 'fuel', 'serwis': 'maintenance'}
    table = tables.get(kind)
    if table:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute(f'DELETE FROM {table} WHERE id = %s', (eid,))
        conn.commit()
        cur.close()
        AuditService.log('Usunięcie', kind.capitalize(), f"Usunięto z tabeli {table} ID: {eid}")
        flash('Wpis usunięty.', 'success')
    referrer = request.referrer or url_for('main.dashboard')
    return redirect(referrer)