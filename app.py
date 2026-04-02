import os
import secrets

from flask import Flask, abort, render_template, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.config import get_config
from backend.db import check_db_health, register_db


def create_app(config_class=None):
    if config_class is None:
        config_class = get_config()

    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Poprawiony CSRF (nagłówek fetch + fallback formdata)
    @app.before_request
    def csrf_protect():
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            token = session.get("_csrf_token", None)
            request_token = request.headers.get("X-CSRFToken") or request.form.get(
                "_csrf_token"
            )
            if not token or token != request_token:
                abort(403, "Błąd walidacji żądania (niepoprawny token CSRF).")

    @app.context_processor
    def inject_statics():
        def get_hashed_static(filename):
            filepath = os.path.join(app.root_path, "static", filename)
            if os.path.exists(filepath):
                mtime = int(os.path.getmtime(filepath))
                return f"/static/{filename}?v={mtime}"
            return f"/static/{filename}"

        return dict(asset_url=get_hashed_static)

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if "_csrf_token" not in session:
                session["_csrf_token"] = secrets.token_hex(32)
            return session["_csrf_token"]

        return dict(csrf_token=generate_csrf_token)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';"
        )

        if app.debug:
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    register_db(app)

    @app.route("/health", endpoint="health")
    def health():
        if check_db_health():
            return "OK", 200
        return "DB ERROR", 500

    from backend.routes.admin import admin_bp
    from backend.routes.api import api_bp
    from backend.routes.auth import auth_bp
    from backend.routes.fuel import fuel_bp
    from backend.routes.logs import logs_bp
    from backend.routes.main import main_bp
    from backend.routes.maintenance import maintenance_bp
    from backend.routes.report import report_bp
    from backend.routes.trips import trips_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(fuel_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(logs_bp)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Nieobsłużony wyjątek aplikacji: %s", error)
        if request.path.startswith("/api/"):
            return {
                "ok": False,
                "error": "Wystąpił błąd serwera. Spróbuj ponownie.",
            }, 500
        return render_template(
            "error.html",
            title="Wystąpił problem",
            message="Wystąpił nieoczekiwany błąd. Spróbuj ponownie za chwilę.",
        ), 500

    return app


# Gunicorn / Render domyślnie podnosi to jako punkt wejścia:
app = create_app()
