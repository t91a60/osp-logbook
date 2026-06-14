import logging

import psycopg2

from backend.db import get_cursor, get_pool

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def log(
        action: str,
        obj_name: str,
        details: str,
        *,
        user_id: int | None = None,
        username: str | None = None,
    ) -> None:
        """
        Zapisuje zdarzenie w audycie w niezależnej transakcji, aby
        nie zaburzać i nie przedwcześnie commitować głównej transakcji zgłoszenia HTTP.
        """
        pool = get_pool()
        conn = None
        try:
            # Pobieramy oddzielne, niezależne połączenie dla audytu
            conn = pool.getconn()
            conn.autocommit = False
            with get_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO audit_log (user_id, username, action, object, details)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, username, action, obj_name, details))
            conn.commit()
        except psycopg2.Error as e:
            if conn is not None and not conn.closed:
                conn.rollback()
            logger.error("Nie udało się zapisać audytu: %s", e)
        finally:
            if conn is not None:
                pool.putconn(conn, close=conn.closed)
