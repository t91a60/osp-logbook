from backend.db import get_db, get_cursor
from backend.services.audit_service import AuditService


class VehicleService:
    @staticmethod
    def delete_vehicle(vehicle_id, user_id=None):
        conn = get_db()
        try:
            with get_cursor(conn) as cur:
                # Soft delete: sets active = 0 (false)
                cur.execute('UPDATE vehicles SET active = 0 WHERE id = %s', (vehicle_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        AuditService.log('Usunięcie', 'Pojazd', f"Usunięto (miękko) pojazd ID: {vehicle_id}")
