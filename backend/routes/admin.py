from flask import render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required

def register_routes(app):
    @app.route('/pojazdy', methods=['GET', 'POST'], endpoint='vehicles')
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
            flash('Pojazd dodany.', 'success')
            cur.close()
            return redirect(url_for('vehicles'))

        cur.execute('SELECT * FROM vehicles ORDER BY active DESC, name')
        vlist = cur.fetchall()
        cur.close()
        return render_template('vehicles.html', vehicles=vlist)

    @app.route('/pojazdy/<int:vid>/toggle', methods=['POST'], endpoint='toggle_vehicle')
    @login_required
    def toggle_vehicle_view(vid):
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('SELECT active FROM vehicles WHERE id = %s', (vid,))
        v = cur.fetchone()
        if v:
            cur.execute('UPDATE vehicles SET active = %s WHERE id = %s',
                         (0 if v['active'] else 1, vid))
            conn.commit()
        cur.close()
        return redirect(url_for('vehicles'))

    @app.route('/uzytkownicy', methods=['GET', 'POST'], endpoint='users')
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
                    flash('Hasło zmienione.', 'success')
                else:
                    flash('Hasło musi mieć co najmniej 4 znaki.', 'error')
            cur.close()
            return redirect(url_for('users'))

        cur.execute('SELECT id, username, display_name FROM users ORDER BY display_name')
        all_users = cur.fetchall()
        cur.close()
        return render_template('users.html', users=all_users)

    @app.route('/usun/<string:kind>/<int:eid>', methods=['POST'], endpoint='delete_entry')
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
            flash('Wpis usunięty.', 'success')
        referrer = request.referrer or url_for('dashboard')
        return redirect(referrer)