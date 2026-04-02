from backend.db import get_pool, get_cursor
from flask import session
from typing import Any, Optional
import psycopg2
import logging

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log(action: str, obj_name: str, details: str) -> None:
        """
        Zapisuje zdarzenie w audycie w niezależnej transakcji, aby 
        nie zaburzać i nie przedwcześnie commitować głównej transakcji zgłoszenia HTTP.
        """
        user_id: Optional[Any] = session.get('user_id')
        username: Optional[str] = session.get('username')
        
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
            logger.error(f"Nie udało się zapisać audytu: {e}")
        finally:
            if conn is not None:
                pool.putconn(conn, close=conn.closed)
