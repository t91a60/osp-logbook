import os
import logging

import psycopg2
from werkzeug.security import generate_password_hash
from flask import Flask

from backend.db import get_pool, get_cursor

logger = logging.getLogger(__name__)


def ensure_bootstrap_admin(_app: Flask) -> None:
    """Create or update bootstrap admin from env vars when explicitly configured."""
    username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME', 'admin').strip()
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '').strip()
    display_name = os.environ.get('BOOTSTRAP_ADMIN_DISPLAY_NAME', 'Administrator').strip() or 'Administrator'
    force_reset = os.environ.get('BOOTSTRAP_ADMIN_FORCE_RESET', '0') == '1'

    if not username or not password:
        return

    conn = None
    pool = get_pool()
    try:
        conn = pool.getconn()
        conn.autocommit = False
        with get_cursor(conn) as cur:
            cur.execute(
                'SELECT id FROM users WHERE username = %s',
                (username,),
            )
            row = cur.fetchone()

            if row and not force_reset:
                conn.rollback()
                return

            pw_hash = generate_password_hash(password)
            if row:
                cur.execute(
                    '''
                    UPDATE users
                    SET password = %s,
                        display_name = %s,
                        is_admin = TRUE
                    WHERE id = %s
                    ''',
                    (pw_hash, display_name, row['id']),
                )
            else:
                cur.execute(
                    '''
                    INSERT INTO users (username, password, display_name, is_admin)
                    VALUES (%s, %s, %s, TRUE)
                    ''',
                    (username, pw_hash, display_name),
                )
        conn.commit()
    except psycopg2.errors.UndefinedTable:
        if conn is not None and not conn.closed:
            conn.rollback()
        logger.warning('Bootstrap admin skipped: users table not available yet')
        return
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        logger.exception('Bootstrap admin initialization failed')
        raise
    finally:
        if conn is not None:
            pool.putconn(conn, close=conn.closed)
