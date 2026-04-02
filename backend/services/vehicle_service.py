from backend.db import get_db, get_cursor
from backend.services.audit_service import AuditService

class VehicleService:
    @staticmethod
    def delete_vehicle(vehicle_id, user_id=None):
        conn = get_db()
        cur = get_cursor(conn)
        
        # Soft delete: sets active = 0 (false)
        cur.execute('UPDATE vehicles SET active = 0 WHERE id = %s', (vehicle_id,))
        conn.commit()
        cur.close()
        
        AuditService.log('Usunięcie', 'Pojazd', f"Usunięto (miękko) pojazd ID: {vehicle_id}")
