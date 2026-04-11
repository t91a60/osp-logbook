from flask import render_template, request, flash, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash
from psycopg2 import IntegrityError
from backend.db import get_db, get_cursor
from backend.helpers import login_required, admin_required
from backend.services.vehicle_service import VehicleService

MIN_PASSWORD_LEN = 8


def register_routes(app):
    from app import limiter

    def _delete_vehicle_or_error(cur, vid):
        cur.execute('SELECT id FROM vehicles WHERE id = %s', (vid,))
        vehicle = cur.fetchone()
        if not vehicle:
            return 'Pojazd nie istnieje.'

        cur.execute(
            'SELECT (SELECT COUNT(*) FROM trips WHERE vehicle_id = %s) + '
            '       (SELECT COUNT(*) FROM fuel WHERE vehicle_id = %s) + '
            '       (SELECT COUNT(*) FROM maintenance WHERE vehicle_id = %s) AS count',
            (vid, vid, vid)
        )
        ref_count = cur.fetchone()['count']
        if ref_count:
            return (
                'Nie można usunąć pojazdu — posiada przypisane wpisy (wyjazdy/tankowania/serwis). '
                'Najpierw usuń powiązane wpisy.'
            )

        try:
            VehicleService.delete_vehicle(vid, session.get('user_id'))
        except Exception:
            return 'Nie udało się usunąć pojazdu. Spróbuj ponownie.'

        return None

    @app.route('/pojazdy', methods=['GET', 'POST'], endpoint='vehicles')
    @admin_required
    def vehicles():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            if request.method == 'POST':
                f = request.form
                cur.execute(
                    'INSERT INTO vehicles (name, plate, type) VALUES (%s, %s, %s)',
                    (f['name'].strip(), f.get('plate', '').strip(), f.get('type', '').strip())
                )
                conn.commit()
                flash('Pojazd dodany.', 'success')
                return redirect(url_for('vehicles'))

            cur.execute('SELECT * FROM vehicles ORDER BY name')
            vlist = cur.fetchall()
        finally:
            cur.close()
        return render_template('vehicles.html', vehicles=vlist)

    @app.route('/pojazdy/<int:vid>/toggle', methods=['POST'], endpoint='toggle_vehicle')
    @admin_required
    def toggle_vehicle_view(vid):
        conn = get_db()
        cur = get_cursor(conn)
        try:
            error = _delete_vehicle_or_error(cur, vid)
            if error:
                flash(error, 'error')
            else:
                flash('Pojazd usunięty.', 'success')
        finally:
            cur.close()
        return redirect(url_for('vehicles'))

    @app.route('/uzytkownicy', methods=['GET', 'POST'], endpoint='users')
    @admin_required
    def users():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            if request.method == 'POST':
                action = request.form.get('action')
                if action == 'add':
                    pw = request.form.get('password', '')
                    if len(pw) < MIN_PASSWORD_LEN:
                        flash(f'Hasło musi mieć co najmniej {MIN_PASSWORD_LEN} znaków.', 'error')
                    else:
                        try:
                            is_admin = request.form.get('is_admin') == '1'
                            cur.execute(
                                'INSERT INTO users (username, password, display_name, is_admin) VALUES (%s, %s, %s, %s)',
                                (request.form['username'].strip(),
                                 generate_password_hash(pw),
                                 request.form['display_name'].strip(),
                                 is_admin)
                            )
                            conn.commit()
                            flash('Użytkownik dodany.', 'success')
                        except IntegrityError:
                            conn.rollback()
                            flash('Login już istnieje.', 'error')
                elif action == 'change_pw':
                    uid = request.form.get('uid')
                    new_pw = request.form.get('new_password', '')
                    if uid and len(new_pw) >= MIN_PASSWORD_LEN:
                        cur.execute('UPDATE users SET password = %s WHERE id = %s',
                                    (generate_password_hash(new_pw), uid))
                        conn.commit()
                        flash('Hasło zmienione.', 'success')
                    else:
                        flash(f'Hasło musi mieć co najmniej {MIN_PASSWORD_LEN} znaków.', 'error')
                elif action == 'delete':
                    uid = request.form.get('uid')
                    if not uid:
                        flash('Brak ID użytkownika.', 'error')
                        return redirect(url_for('users'))

                    try:
                        uid_int = int(uid)
                    except (TypeError, ValueError):
                        flash('Nieprawidłowe ID użytkownika.', 'error')
                        return redirect(url_for('users'))

                    if uid_int == session.get('user_id'):
                        flash('Nie możesz usunąć własnego konta.', 'error')
                        return redirect(url_for('users'))

                    cur.execute('SELECT id, username, is_admin FROM users WHERE id = %s', (uid_int,))
                    target = cur.fetchone()
                    if not target:
                        flash('Użytkownik nie istnieje.', 'error')
                        return redirect(url_for('users'))

                    if target.get('is_admin'):
                        cur.execute('SELECT COUNT(*) AS count FROM users WHERE is_admin = TRUE AND id <> %s', (uid_int,))
                        remaining_admins = cur.fetchone()['count']
                        if remaining_admins <= 0:
                            flash('Nie można usunąć ostatniego administratora.', 'error')
                            return redirect(url_for('users'))

                    cur.execute('DELETE FROM users WHERE id = %s', (uid_int,))
                    conn.commit()
                    flash('Użytkownik usunięty.', 'success')
                return redirect(url_for('users'))

            cur.execute('SELECT id, username, display_name, is_admin FROM users ORDER BY display_name')
            all_users = cur.fetchall()
        finally:
            cur.close()
        return render_template('users.html', users=all_users)

    @app.route('/pojazdy/<int:vid>/usun', methods=['POST'], endpoint='delete_vehicle')
    @admin_required
    @limiter.limit('30 per minute')
    def delete_vehicle(vid):
        conn = get_db()
        cur = get_cursor(conn)
        try:
            error = _delete_vehicle_or_error(cur, vid)
            if error:
                flash(error, 'error')
            else:
                flash('Pojazd usunięty.', 'success')
        finally:
            cur.close()
        return redirect(url_for('vehicles'))

    @app.route('/usun/<string:kind>/<int:eid>', methods=['POST'], endpoint='delete_entry')
    @login_required
    def delete_entry_view(kind, eid):
        tables = {'wyjazd': 'trips', 'tankowanie': 'fuel', 'serwis': 'maintenance'}
        table = tables.get(kind)
        if not table:
            abort(404)

        conn = get_db()
        cur = get_cursor(conn)
        try:
            # Pobierz wpis, żeby sprawdzić autora
            cur.execute(f'SELECT added_by FROM {table} WHERE id = %s', (eid,))
            entry = cur.fetchone()
            if not entry:
                flash('Wpis nie istnieje.', 'error')
                return redirect(request.referrer or url_for('dashboard'))

            # Może usunąć autor wpisu LUB admin
            if entry['added_by'] != session['username'] and not session.get('is_admin'):
                abort(403)

            cur.execute(f'DELETE FROM {table} WHERE id = %s', (eid,))
            conn.commit()
        finally:
            cur.close()

        flash('Wpis usunięty.', 'success')
        return redirect(request.referrer or url_for('dashboard'))
