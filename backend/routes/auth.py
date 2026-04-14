from flask import request, session, redirect, url_for, flash, render_template
from werkzeug.security import check_password_hash
import secrets
from backend.db import get_db, get_cursor


def register_routes(app):
    # Import tutaj, żeby uniknąć circular import (app importuje routes, routes importuje app)
    from app import limiter

    @app.route('/login', methods=['GET', 'POST'], endpoint='login')
    @limiter.limit("10 per minute; 30 per hour", error_message="Zbyt wiele prób logowania. Spróbuj za chwilę.")
    def login():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            conn = get_db()
            cur = get_cursor(conn)
            try:
                cur.execute(
                    'SELECT id, username, password, display_name, is_admin FROM users WHERE username = %s',
                    (username,)
                )
                user = cur.fetchone()
            finally:
                cur.close()

            if user and check_password_hash(user['password'], password):
                is_admin = bool(user['is_admin'])

                # Backward compatibility: older deployments could have an
                # existing 'admin' user created before the is_admin flag.
                # Auto-repair the flag at login so admin routes work again.
                if user['username'] == 'admin' and not is_admin:
                    cur = get_cursor(conn)
                    try:
                        cur.execute(
                            'UPDATE users SET is_admin = TRUE WHERE id = %s RETURNING is_admin',
                            (user['id'],)
                        )
                        row = cur.fetchone()
                        conn.commit()
                        is_admin = bool(row['is_admin']) if row else True
                    finally:
                        cur.close()

                # Reset previous session state to reduce session fixation risk.
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['display_name'] = user['display_name']
                session['is_admin'] = is_admin
                session['_csrf_token'] = secrets.token_hex(32)
                return redirect(url_for('dashboard'))

            flash('Nieprawidłowy login lub hasło.', 'error')
        return render_template('login.html')

    @app.route('/logout', endpoint='logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))
