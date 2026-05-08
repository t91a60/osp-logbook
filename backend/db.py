import os
import time
import logging
from collections.abc import Callable

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from flask import g, Flask

logger = logging.getLogger(__name__)

_db_pool: SimpleConnectionPool | None = None


def _create_pool() -> SimpleConnectionPool:
    """Create a new connection pool."""
    return SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=os.environ.get('DATABASE_URL'),
        sslmode='require',
        connect_timeout=10,
        application_name='osp-logbook',
        options='-c statement_timeout=30000',
    )


def get_pool() -> SimpleConnectionPool:
    global _db_pool
    if _db_pool is None:
        _db_pool = _create_pool()
    return _db_pool


def reset_pool() -> SimpleConnectionPool:
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
        last_error = None
        for attempt in range(1, 4):
            try:
                conn = get_pool().getconn()
                conn.autocommit = False
                g.db = conn
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                last_error = exc
                logger.warning("DB connection failed (attempt %d/3): %s", attempt, exc)
                reset_pool()
                if attempt < 3:
                    time.sleep(1)
        else:
            logger.error("DB connection failed after 3 attempts: %s", last_error)
            raise last_error
    return g.db


def get_cursor(conn):
    """Returns a cursor with RealDictCursor for dict-like row access."""
    return conn.cursor(cursor_factory=RealDictCursor)


def close_db(e: BaseException | None = None) -> None:
    db = g.pop('db', None)
    if db is not None:
        pool = _db_pool
        try:
            if not db.closed:
                try:
                    db.rollback()
                except Exception:
                    pass
            if pool is not None:
                try:
                    pool.putconn(db, close=bool(db.closed))
                except Exception:
                    try:
                        pool.putconn(db, close=True)
                    except Exception:
                        pass
            else:
                try:
                    db.close()
                except Exception:
                    pass
        except Exception:
            try:
                db.close()
            except Exception:
                pass


def _retry_on_connection_failure[T](func: Callable[[], T], max_retries: int = 3, delay: int = 1) -> T:
    """Retry a function on connection failure."""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")
    for attempt in range(max_retries):
        try:
            return func()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            if attempt < max_retries - 1:
                logger.warning("DB connection failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
                time.sleep(delay)
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
    raise RuntimeError("Unreachable")


def check_db_health() -> bool:
    """Check if the database connection is healthy."""
    try:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute("SELECT 1")
            return True
        finally:
            cur.close()
    except Exception:
        logger.exception("DB health check failed")
        return False


def _fetch_schema_version(conn) -> int | None:
    with get_cursor(conn) as cur:
        cur.execute(
            '''
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'schema_version'
            ) AS exists;
            '''
        )
        exists = bool(cur.fetchone()['exists'])
        if not exists:
            return None

        cur.execute('SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;')
        row = cur.fetchone()
        return int(row['version']) if row else None


def log_schema_version() -> None:
    conn = None
    try:
        pool = get_pool()
        conn = pool.getconn()
        conn.autocommit = True
        version = _fetch_schema_version(conn)
        if version is None:
            logger.warning('schema_version table missing or empty')
        else:
            logger.info('Schema version at startup: %s', version)
    except Exception:
        logger.exception('Failed to log schema_version at startup')
    finally:
        if conn is not None:
            pool.putconn(conn, close=conn.closed)


def init_db() -> None:
    """Validate baseline schema and ensure admin account is initialized."""
    conn = None
    pool = get_pool()
    try:
        conn = pool.getconn()
        conn.autocommit = False

        with get_cursor(conn) as cur:
            cur.execute(
                '''
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'users'
                ) AS exists;
                '''
            )
            if not bool(cur.fetchone()['exists']):
                conn.rollback()
                raise RuntimeError('Run: psql $DATABASE_URL -f schema.sql first')

            cur.execute('SELECT id, password FROM users WHERE username = %s;', ('admin',))
            admin_row = cur.fetchone()
            needs_admin_password = admin_row is None or admin_row['password'] == 'CHANGE_ME_RUN_FLASK_INIT'
            if needs_admin_password and not os.environ.get('BOOTSTRAP_ADMIN_PASSWORD'):
                conn.rollback()
                raise RuntimeError('Set BOOTSTRAP_ADMIN_PASSWORD before running init_db()')

            generated_password = generate_password_hash(os.environ['BOOTSTRAP_ADMIN_PASSWORD']) if needs_admin_password else None

            if admin_row is None:
                cur.execute(
                    '''
                    INSERT INTO users (username, password, display_name, role, is_admin)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    ''',
                    ('admin', generated_password, 'Administrator', 'admin', True),
                )
                cur.fetchone()
            elif admin_row['password'] == 'CHANGE_ME_RUN_FLASK_INIT':
                cur.execute(
                    '''
                    UPDATE users
                    SET password = %s,
                        display_name = %s,
                        role = %s,
                        is_admin = %s
                    WHERE id = %s;
                    ''',
                    (generated_password, 'Administrator', 'admin', True, admin_row['id']),
                )

        conn.commit()
        version = _fetch_schema_version(conn)
        if version is None:
            logger.warning('schema_version table missing or empty')
        else:
            logger.info('Schema version at startup: %s', version)
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            pool.putconn(conn, close=conn.closed)


def register_db(app: Flask) -> None:
    """Registers DB teardown cleanup with the app context."""
    app.teardown_appcontext(close_db)
    log_schema_version()
