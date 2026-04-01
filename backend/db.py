import os
import time
import logging
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from flask import g, current_app
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

_db_pool = None

def _create_pool():
    """Create a new connection pool."""
    return SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=os.environ.get('DATABASE_URL'),
        sslmode='require',
        connect_timeout=5
    )

def get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = _create_pool()
    return _db_pool

def reset_pool():
    """Close all connections and create a fresh pool."""
    global _db_pool
    if _db_pool is not None:
        try:
            _db_pool.closeall()
        except Exception:
            pass
    _db_pool = _create_pool()
    return _db_pool

def get_db():
    if 'db' not in g:
        g.db = get_pool().getconn()
        g.db.autocommit = False
    return g.db

def get_cursor(conn):
    """Returns a cursor with RealDictCursor for dict-like row access."""
    return conn.cursor(cursor_factory=RealDictCursor)

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            if db.closed:
                get_pool().putconn(db, close=True)
            else:
                get_pool().putconn(db)
        except Exception:
            try:
                get_pool().putconn(db, close=True)
            except Exception:
                pass

def _retry_on_connection_failure(func, max_retries=3, delay=1):
    """Retry a function on connection failure (e.g., DB restart on Render)."""
    for attempt in range(max_retries):
        try:
            return func()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            if attempt < max_retries - 1:
                logger.warning("DB connection failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
                time.sleep(delay)
                # Oczyszczenie w czysty sposób
                close_db()
                reset_pool()
            else:
                logger.error("DB connection failed after %d attempts: %s", max_retries, e)
                raise

def check_db_health():
    """Check if the database connection is healthy."""
    try:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute("SELECT 1")
        cur.close()
        return True
    except Exception:
        logger.exception("DB health check failed")
        return False

def register_db(app):
    """Registers DB teardown and initialization routines with the app context."""
    app.teardown_appcontext(close_db)
