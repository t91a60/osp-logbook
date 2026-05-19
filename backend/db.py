import os
import time
import logging
import re
from pathlib import Path

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from flask import g, Flask
import sqlparse

logger = logging.getLogger(__name__)

_db_pool: SimpleConnectionPool | None = None
ADMIN_PLACEHOLDER_PASSWORD = 'CHANGE_ME_RUN_FLASK_INIT'
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / 'migrations'
_MIGRATION_FILE_RE = re.compile(r'^(?P<version>\d+)_.*\.sql$')
MIGRATIONS_LOCK_ID = 91726051


def _create_pool() -> SimpleConnectionPool:
    """Create a new connection pool."""
    return SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=os.environ.get('DATABASE_URL'),
        sslmode='require',
        connect_timeout=10,
        application_name='osp-logbook',
        # Enable TCP keepalives to avoid Neon "freeze" cold-start latency.
        # Neon suspends connections after brief idle periods; setting
        # keepalives_idle and keepalives_interval reduces the chance of
        # catching the first request while the DB is thawing (300-500ms spikes).
        keepalives_idle=60,
        keepalives_interval=10,
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


def _discover_sql_migrations() -> list[tuple[int, Path]]:
    migrations: list[tuple[int, Path]] = []
    seen_versions: set[int] = set()

    if not MIGRATIONS_DIR.exists():
        return migrations

    for path in sorted(MIGRATIONS_DIR.glob('*.sql')):
        match = _MIGRATION_FILE_RE.match(path.name)
        if not match:
            continue

        version = int(match.group('version'))
        if version in seen_versions:
            raise RuntimeError(f'Duplicate migration version detected: {version}')
        seen_versions.add(version)
        migrations.append((version, path))

    return migrations


def apply_pending_migrations() -> None:
    migrations = _discover_sql_migrations()
    if not migrations:
        return

    conn = None
    pool = get_pool()
    try:
        conn = pool.getconn()
        conn.autocommit = False

        with get_cursor(conn) as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s);', (MIGRATIONS_LOCK_ID,))
            current_version = _fetch_schema_version(conn)
            if current_version is None:
                raise RuntimeError('schema_version table missing or empty; run schema.sql first')

            pending = [(version, path) for version, path in migrations if version > current_version]
            if not pending:
                conn.rollback()
                return

            for version, path in pending:
                migration_sql = path.read_text(encoding='utf-8')
                for statement in sqlparse.split(migration_sql):
                    statement = statement.strip()
                    if statement:
                        try:
                            cur.execute(statement)
                        except Exception as exc:
                            statement_preview = statement if len(statement) <= 160 else f'{statement[:157]}...'
                            raise RuntimeError(
                                f'Failed applying migration {version} ({path.name}): {statement_preview}'
                            ) from exc
                cur.execute('INSERT INTO schema_version (version) VALUES (%s);', (version,))

        conn.commit()
        logger.info(
            'Applied %d pending migrations (schema_version %d -> %d)',
            len(pending),
            current_version,
            pending[-1][0],
        )
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            pool.putconn(conn, close=conn.closed)


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
            admin_password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')

            if admin_row is None:
                if not admin_password:
                    conn.rollback()
                    raise RuntimeError('Set BOOTSTRAP_ADMIN_PASSWORD before running init_db()')
                generated_password = generate_password_hash(admin_password)
            elif admin_row['password'] == ADMIN_PLACEHOLDER_PASSWORD:
                if not admin_password:
                    conn.rollback()
                    raise RuntimeError('Set BOOTSTRAP_ADMIN_PASSWORD before running init_db()')
                generated_password = generate_password_hash(admin_password)
            else:
                # Admin already has a real (bcrypt/scrypt) hash — nothing to do.
                generated_password = None

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
            elif admin_row['password'] == ADMIN_PLACEHOLDER_PASSWORD:
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
    try:
        apply_pending_migrations()
        logger.info('Database migrations checked at startup')
    except (psycopg2.Error, RuntimeError) as exc:
        logger.warning(
            'apply_pending_migrations() failed during register_db(); app will continue without applying pending migrations: %s',
            exc,
        )
        return
    try:
        init_db()
    except (psycopg2.Error, RuntimeError) as exc:
        logger.warning('init_db() failed during register_db(); app will continue without startup DB initialization: %s', exc)
        return
    try:
        log_schema_version()
    except (psycopg2.Error, RuntimeError) as exc:
        logger.warning('Failed to log schema_version after init_db(); continuing startup: %s', exc)
