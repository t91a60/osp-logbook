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
                # Close broken connection from Flask g and reset pool
                db = g.pop('db', None)
                if db is not None:
                    try:
                        get_pool().putconn(db, close=True)
                    except Exception:
                        pass
                reset_pool()
            else:
                logger.error("DB connection failed after %d attempts: %s", max_retries, e)
                raise

def init_db():
    def _init():
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    username     TEXT UNIQUE NOT NULL,
                    password     TEXT NOT NULL,
                    display_name TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vehicles (
                    id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    name   TEXT NOT NULL,
                    plate  TEXT DEFAULT '',
                    type   TEXT DEFAULT '',
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS trips (
                    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    date       TEXT NOT NULL,
                    driver     TEXT NOT NULL,
                    odo_start  INTEGER,
                    odo_end    INTEGER,
                    purpose    TEXT NOT NULL,
                    notes      TEXT DEFAULT '',
                    added_by   TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS fuel (
                    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    date       TEXT NOT NULL,
                    driver     TEXT NOT NULL,
                    odometer   INTEGER,
                    liters     REAL NOT NULL,
                    cost       REAL,
                    notes      TEXT DEFAULT '',
                    added_by   TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS maintenance (
                    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    vehicle_id  INTEGER NOT NULL REFERENCES vehicles(id),
                    date        TEXT NOT NULL,
                    odometer    INTEGER,
                    description TEXT NOT NULL,
                    cost        REAL,
                    notes       TEXT DEFAULT '',
                    added_by    TEXT DEFAULT '',
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'maintenance'")
            existing_columns = {row['column_name'] for row in cur.fetchall()}

            if 'status' not in existing_columns:
                cur.execute("ALTER TABLE maintenance ADD COLUMN status TEXT DEFAULT 'pending'")
            if 'priority' not in existing_columns:
                cur.execute("ALTER TABLE maintenance ADD COLUMN priority TEXT DEFAULT 'medium'")
            if 'due_date' not in existing_columns:
                cur.execute("ALTER TABLE maintenance ADD COLUMN due_date TEXT")

            cur.execute('SELECT 1 FROM users LIMIT 1')
            if not cur.fetchone():
                cur.execute(
                    'INSERT INTO users (username, password, display_name) VALUES (%s, %s, %s)',
                    ('admin', generate_password_hash('admin123'), 'Administrator')
                )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("init_db error")
            raise
        finally:
            cur.close()

    _retry_on_connection_failure(_init)

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
    with app.app_context():
        init_db()