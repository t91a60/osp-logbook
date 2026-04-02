import os
import time
import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from flask import g
from typing import Optional, Any

logger = logging.getLogger(__name__)

_db_pool: Optional[ThreadedConnectionPool] = None

def _create_pool() -> ThreadedConnectionPool:
    """Tworzy nową pulę połączeń z bazą danych bezpieczną dla wątków."""
    return ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=os.environ.get('DATABASE_URL'),
        sslmode='require',
        connect_timeout=5
    )

def get_pool() -> ThreadedConnectionPool:
    global _db_pool
    if _db_pool is None:
        _db_pool = _create_pool()
    return _db_pool

def reset_pool() -> ThreadedConnectionPool:
    """Zamyka wszystkie połączenia i tworzy nową pulę."""
    global _db_pool
    if _db_pool is not None:
        try:
            _db_pool.closeall()
        except psycopg2.Error as e:
            logger.warning(f"Error while closing pool: {e}")
    _db_pool = _create_pool()
    return _db_pool

def get_db() -> Any:
    """Pobiera połączenie DB podłączone do cyklu życia żądania z autocommit=False."""
    if 'db' not in g:
        g.db = get_pool().getconn()
        g.db.autocommit = False
    return g.db

def get_cursor(conn) -> RealDictCursor:
    """Zwraca kursor z RealDictCursor umożliwiający dostęp jak ze słownika."""
    return conn.cursor(cursor_factory=RealDictCursor)

def close_db(e: Optional[Exception] = None) -> None:
    """Czyste zamknięcie połączenia pod koniec żądania HTTP."""
    db = g.pop('db', None)
    if db is not None:
        pool = get_pool()
        try:
            # Reverting pending transaction if exception occurred
            if e is not None and not db.closed:
                db.rollback()
            pool.putconn(db, close=db.closed)
        except psycopg2.Error as err:
            logger.error(f"Failed to cleanly return connection to pool: {err}")
            # Zapewnienie, że w razie awarii złącze nie wraca zanieczyszczone
            try:
                pool.putconn(db, close=True)
            except psycopg2.Error:
                pass


def _retry_on_connection_failure(func, max_retries: int = 3, delay: int = 1) -> Any:
    """Retry wrapper, if connection failure (e.g. Render restart) drop pool and retry."""
    for attempt in range(max_retries):
        try:
            return func()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"DB connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(delay)
                # Oczyszczenie brudnego połączenia i odświeżenie puli
                close_db()
                reset_pool()
            else:
                logger.error(f"DB connection failed after {max_retries} attempts: {e}")
                raise

def check_db_health() -> bool:
    """Healthcheck połączenia do DB."""
    try:
        conn = get_pool().getconn()
        with get_cursor(conn) as cur:
            cur.execute("SELECT 1")
        get_pool().putconn(conn)
        return True
    except psycopg2.Error as e:
        logger.exception(f"DB health check failed: {e}")
        return False

def register_db(app) -> None:
    """Rejestruje rutynę zamykania bazy z kontekstem aplikacji."""
    app.teardown_appcontext(close_db)
