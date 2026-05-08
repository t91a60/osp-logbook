import os
import time
import logging
from collections.abc import Callable

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from flask import g, Flask

logger = logging.getLogger(__name__)

_db_pool: SimpleConnectionPool | None = None


def _create_pool() -> SimpleConnectionPool:
    """Create a new connection pool."""
    minconn = max(1, int(os.environ.get('DB_POOL_MIN', '1')))
    maxconn = int(os.environ.get('DB_POOL_MAX', '10'))
    if maxconn < minconn:
        maxconn = minconn

    return SimpleConnectionPool(
        minconn=minconn,
        maxconn=maxconn,
        dsn=os.environ.get('DATABASE_URL'),
        sslmode='require',
        connect_timeout=5,
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
    """Retry a function on connection failure (e.g., DB restart on Render)."""
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


def register_db(app: Flask) -> None:
    """Registers DB teardown cleanup with the app context."""
    app.teardown_appcontext(close_db)
