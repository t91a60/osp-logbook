"""
Service layer — thin orchestration only.
Business logic lives in backend/infrastructure/repositories/.
Services add: audit logging, cross-repository coordination.
"""

from backend.application import UseCaseFactory
from backend.services.audit_service import AuditService
from backend.services.cache_service import invalidate_prefix


class TripService:
    @staticmethod
    def add_trip(
        vehicle_id: int | str | None,
        date_val: str,
        driver: str,
        odo_start: int | str | None,
        odo_end: int | str | None,
        purpose: str,
        notes: str,
        added_by: str,
        *,
        time_start: str | None = None,
        time_end: str | None = None,
        equipment_used: list[dict] | None = None,
    ) -> None:
        trip_repo = UseCaseFactory.get_trip_repo()
        trip_repo.add(
            vehicle_id=vehicle_id,
            date_val=date_val,
            driver=driver,
            odo_start=odo_start,
            odo_end=odo_end,
            purpose=purpose,
            notes=notes,
            added_by=added_by,
            time_start=time_start,
            time_end=time_end,
            equipment_used=equipment_used,
        )
        AuditService.log('Dodanie', 'Wyjazd', f'Pojazd ID: {vehicle_id}, Kierowca: {driver}, Data: {date_val}')
        # Invalidate report caches for this vehicle (keys: report:{vehicle_id}:<period>)
        try:
            invalidate_prefix(f'report:{vehicle_id}:')
        except Exception:
            # Non-fatal: cache invalidation is best-effort
            pass
