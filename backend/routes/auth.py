import secrets
from datetime import UTC, datetime

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from backend.db import get_cursor, get_db


def register_routes(app):
    from app import get_limiter
    limiter = get_limiter()

    @app.route('/login', methods=['GET', 'POST'], endpoint='login')
    @limiter.limit(
        "10 per minute; 30 per hour",
        methods=['POST'],
        error_message="Zbyt wiele prób logowania. Spróbuj za chwilę.",
    )
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
                    'SELECT id, username, password, display_name, is_admin'
                    ' FROM users WHERE username = %s',
                    (username,)
                )
                user = cur.fetchone()
            finally:
                cur.close()

            if user and check_password_hash(user['password'], password):
                is_admin = bool(user['is_admin'])

                if user['username'] == 'admin' and not is_admin:
                    cur = get_cursor(conn)
                    try:
                        cur.execute(
                            'UPDATE users SET is_admin = TRUE'
                            ' WHERE id = %s RETURNING is_admin',
                            (user['id'],)
                        )
                        row = cur.fetchone()
                        conn.commit()
                        is_admin = bool(row['is_admin']) if row else True
                    finally:
                        cur.close()

                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['display_name'] = user['display_name']
                session['is_admin'] = is_admin
                session['_csrf_token'] = secrets.token_hex(32)
                session['session_started_at'] = datetime.now(UTC).isoformat()
                session.permanent = True
                return redirect(url_for('dashboard'))

            flash('Nieprawidłowy login lub hasło.', 'error')
        return render_template('login.html')

    @app.route('/logout', methods=['POST'], endpoint='logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))
