"""
Service layer — thin orchestration only.
Business logic lives in backend/infrastructure/repositories/.
Services add: audit logging, cross-repository coordination.
"""

from backend.infrastructure.repositories.trips import TripRepository
from backend.services.audit_service import AuditService


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
        TripRepository.add(
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
