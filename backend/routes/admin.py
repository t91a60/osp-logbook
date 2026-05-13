from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, session, url_for
from psycopg2 import IntegrityError
from psycopg2 import sql
from werkzeug.security import generate_password_hash

from backend.application import UseCaseFactory
from backend.db import get_cursor, get_db
from backend.domain.exceptions import ForbiddenError, NotFoundError
from backend.helpers import admin_required, login_required
from backend.services.audit_service import AuditService
from backend.services.cache_service import invalidate_prefix

MIN_PASSWORD_LEN = 8


def register_routes(app):
    from app import limiter

    # ── Vehicle CRUD (admin only) ─────────────────────────────────────────

    @app.route('/pojazdy', methods=['GET', 'POST'], endpoint='vehicles')
    @admin_required
    def vehicles():
        vehicle_repo = UseCaseFactory.get_vehicle_repo()

        if request.method == 'POST':
            f = request.form
            name = f.get('name', '').strip()
            if not name:
                flash('Nazwa pojazdu jest wymagana.', 'error')
                return redirect(url_for('vehicles'))
            try:
                vehicle_repo.add(
                    name=name,
                    plate=f.get('plate', '').strip(),
                    type_=f.get('type', '').strip(),
                )
                invalidate_prefix('vehicles:')
                invalidate_prefix('dashboard:')
                AuditService.log('Dodanie', 'Pojazd', f'Nazwa: {name}')
                flash('Pojazd dodany.', 'success')
            except IntegrityError:
                flash('Nie udało się dodać pojazdu. Sprawdź dane.', 'error')
            return redirect(url_for('vehicles'))

        vlist = vehicle_repo.get_all()
        return render_template('vehicles.html', vehicles=vlist)

    @app.route('/pojazdy/<int:vid>/toggle', methods=['POST'], endpoint='toggle_vehicle')
    @admin_required
    def toggle_vehicle_view(vid):
        vehicle_repo = UseCaseFactory.get_vehicle_repo()
        try:
            vehicle_repo.delete(vid)
            invalidate_prefix('vehicles:')
            invalidate_prefix('dashboard:')
            AuditService.log('Usunięcie', 'Pojazd', f'Usunięto pojazd ID: {vid}')
            flash('Pojazd usunięty.', 'success')
        except NotFoundError:
            flash('Pojazd nie istnieje.', 'error')
        except ForbiddenError as exc:
            flash(str(exc), 'error')
        return redirect(url_for('vehicles'))

    @app.route('/pojazdy/<int:vid>/usun', methods=['POST'], endpoint='delete_vehicle')
    @admin_required
    @limiter.limit('30 per minute')
    def delete_vehicle(vid):
        vehicle_repo = UseCaseFactory.get_vehicle_repo()
        try:
            vehicle_repo.delete(vid)
            invalidate_prefix('vehicles:')
            invalidate_prefix('dashboard:')
            AuditService.log('Usunięcie', 'Pojazd', f'Usunięto pojazd ID: {vid}')
            flash('Pojazd usunięty.', 'success')
        except NotFoundError:
            flash('Pojazd nie istnieje.', 'error')
        except ForbiddenError as exc:
            flash(str(exc), 'error')
        return redirect(url_for('vehicles'))

    @app.route('/pojazdy/<int:vid>/edytuj', methods=['GET', 'POST'], endpoint='edit_vehicle')
    @admin_required
    def edit_vehicle(vid):
        vehicle_repo = UseCaseFactory.get_vehicle_repo()
        vehicle = vehicle_repo.get_by_id(vid)
        if not vehicle:
            flash('Pojazd nie istnieje.', 'error')
            return redirect(url_for('vehicles'))

        if request.method == 'POST':
            f = request.form
            name = f.get('name', '').strip()
            if not name:
                flash('Nazwa pojazdu jest wymagana.', 'error')
            else:
                try:
                    vehicle_repo.update(
                        vid=vid,
                        name=name,
                        plate=f.get('plate', '').strip(),
                        type_=f.get('type', '').strip(),
                    )
                    invalidate_prefix('vehicles:')
                    invalidate_prefix('dashboard:')
                    AuditService.log('Edycja', 'Pojazd', f'ID: {vid}, Nazwa: {name}')
                    flash('Pojazd zaktualizowany.', 'success')
                    return redirect(url_for('vehicles'))
                except NotFoundError:
                    flash('Pojazd nie istnieje.', 'error')

        return render_template('vehicle_edit.html', vehicle=vehicle)

    # ── User management (admin only — raw SQL, no UserRepository yet) ─────

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
                        cur.execute(
                            'SELECT COUNT(*) AS count FROM users WHERE is_admin = TRUE AND id <> %s',
                            (uid_int,)
                        )
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

    # ── Legacy generic delete (cross-table, known tech debt) ─────────────

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
            cur.execute(
                sql.SQL('SELECT added_by FROM {} WHERE id = %s').format(sql.Identifier(table)),
                (eid,),
            )
            entry = cur.fetchone()
            if not entry:
                flash('Wpis nie istnieje.', 'error')
                return redirect(request.referrer or url_for('dashboard'))

            if entry['added_by'] != session['username'] and not session.get('is_admin'):
                abort(403)

            cur.execute(
                sql.SQL('DELETE FROM {} WHERE id = %s').format(sql.Identifier(table)),
                (eid,),
            )
            conn.commit()
        finally:
            cur.close()

        flash('Wpis usunięty.', 'success')
        return redirect(request.referrer or url_for('dashboard'))
