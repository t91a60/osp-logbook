from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError


def configure_session_security(app: Flask) -> None:
    if app.config.get('USE_HTTPS'):
        app.config['SESSION_COOKIE_SECURE'] = True
    app.config.setdefault('SESSION_COOKIE_NAME', 'osp_logbook_session')
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')


def _is_json_request() -> bool:
    if request.is_json:
        return True
    accept = (request.headers.get('Accept') or '').lower()
    xrw = (request.headers.get('X-Requested-With') or '').lower()
    return 'application/json' in accept or xrw == 'xmlhttprequest'


def _csrf_failure_response():
    message = 'Sesja wygasła lub token CSRF jest niepoprawny. Odśwież stronę i spróbuj ponownie.'
    if _is_json_request():
        return jsonify({'success': False, 'message': message, 'code': 'csrf_invalid'}), 403

    flash(message, 'error')
    if 'user_id' in session:
        return redirect(request.referrer or url_for('dashboard'))
    return redirect(url_for('login'))


def register_request_guards(app: Flask) -> None:
    @app.before_request
    def csrf_protect():
        g.csp_nonce = secrets.token_urlsafe(16)
        if request.endpoint not in {'login', 'logout', 'health', 'static'}:
            last_seen = session.get('session_started_at')
            if 'user_id' in session and last_seen:
                try:
                    started_at = datetime.fromisoformat(last_seen)
                    lifetime = app.config.get('PERMANENT_SESSION_LIFETIME')
                    ttl_seconds = lifetime.total_seconds() if lifetime else 8 * 3600
                    age_seconds = (datetime.now(UTC) - started_at).total_seconds()
                    if age_seconds > ttl_seconds:
                        session.clear()
                        flash('Sesja wygasła. Zaloguj się ponownie.', 'error')
                        return redirect(url_for('login'))
                except (TypeError, ValueError):
                    session.clear()
                    return redirect(url_for('login'))

        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            token = session.get('_csrf_token')
            if request.is_json:
                req_token = request.headers.get('X-CSRFToken')
            else:
                req_token = (
                    request.form.get('_csrf_token')
                    or request.form.get('csrf_token')
                    or request.headers.get('X-CSRFToken')
                    or request.headers.get('X-CSRF-Token')
                    or request.headers.get('X-XSRF-TOKEN')
                )

            if not token or not req_token:
                return _csrf_failure_response()

            if not hmac.compare_digest(str(token), str(req_token)):
                return _csrf_failure_response()


def register_context_processors(app: Flask) -> None:
    static_root = os.path.realpath(os.path.join(app.root_path, 'static'))

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if '_csrf_token' not in session:
                session['_csrf_token'] = secrets.token_hex(32)
            return session['_csrf_token']

        def asset_url(filename: str) -> str:
            filepath = os.path.realpath(os.path.join(static_root, filename))
            if not filepath.startswith(static_root + os.sep):
                mtime = 0
            else:
                try:
                    mtime = int(os.path.getmtime(filepath))
                except (OSError, ValueError):
                    mtime = 0
            return url_for('static', filename=filename, v=mtime)

        def sw_url() -> str:
            sw_assets = ('sw.js', 'main.css', 'mobile.css', 'login.css', 'app.js', 'manifest.json')
            version_seed = []
            for asset in sw_assets:
                filepath = os.path.realpath(os.path.join(static_root, asset))
                if not filepath.startswith(static_root + os.sep):
                    version_seed.append(f'{asset}:0')
                    continue
                try:
                    mtime = int(os.path.getmtime(filepath))
                except (OSError, ValueError):
                    mtime = 0
                version_seed.append(f'{asset}:{mtime}')
            version_hash = hashlib.sha1('|'.join(version_seed).encode('utf-8')).hexdigest()[:12]
            return url_for('sw', v=version_hash)

        def csp_nonce():
            return getattr(g, 'csp_nonce', '')

        return dict(
            csrf_token=generate_csrf_token, asset_url=asset_url,
            sw_url=sw_url, csp_nonce=csp_nonce,
        )


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def add_security_headers(response):
        nonce = getattr(g, 'csp_nonce', '')
        script_src = "script-src 'self'"
        if nonce:
            script_src = f"{script_src} 'nonce-{nonce}'"

        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response.headers['Content-Security-Policy'] = (
            f"default-src 'self'; {script_src}; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'self'; frame-ancestors 'none';"
        )
        try:
            max_age = int(app.config.get('SEND_FILE_MAX_AGE_DEFAULT', 0))
        except Exception:
            max_age = 0

        if request.path.startswith('/static/') and not app.debug and max_age > 0:
            response.headers['Cache-Control'] = f'public, max-age={max_age}, immutable'
        elif app.debug:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': str(error)}), 400
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('dashboard')), 302

    @app.errorhandler(NotFoundError)
    def handle_not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': str(error)}), 404
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('dashboard')), 302

    @app.errorhandler(ForbiddenError)
    def handle_forbidden(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': str(error)}), 403
        flash(str(error), 'error')
        return redirect(url_for('dashboard')), 302

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception('Unhandled application error')
        if request.path.startswith('/api/'):
            return jsonify({'ok': False, 'error': 'Internal server error'}), 500
        return render_template(
            'error.html',
            title='Błąd serwera',
            message='Wystąpił nieoczekiwany błąd. Spróbuj ponownie.',
        ), 500
