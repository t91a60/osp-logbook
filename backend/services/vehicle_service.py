from backend.db import get_db, get_cursor
from backend.services.audit_service import AuditService


class VehicleService:
    @staticmethod
    def delete_vehicle(vehicle_id, user_id=None):
        conn = get_db()
        try:
            with get_cursor(conn) as cur:
                cur.execute('DELETE FROM vehicles WHERE id = %s', (vehicle_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        AuditService.log('Usunięcie', 'Pojazd', f"Usunięto pojazd ID: {vehicle_id}")
