from backend.db import get_db, get_cursor
from backend.services.audit_service import AuditService
from backend.services.cache_service import invalidate_prefix


class VehicleService:
    @staticmethod
    def delete_vehicle(vehicle_id: int, user_id: int | None = None) -> None:
        conn = get_db()
        try:
            with get_cursor(conn) as cur:
                cur.execute('DELETE FROM vehicles WHERE id = %s', (vehicle_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        invalidate_prefix('vehicles:')
        AuditService.log('Usunięcie', 'Pojazd', f"Usunięto pojazd ID: {vehicle_id}")
