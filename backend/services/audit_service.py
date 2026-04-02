from backend.db import get_db, get_cursor
from flask import session

class AuditService:
    @staticmethod
    def log(action, obj_name, details):
        user_id = session.get('user_id')
        username = session.get('username')
        
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO audit_log (user_id, username, action, object, details)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, username, action, obj_name, details))
        conn.commit()
        cur.close()
