"""
Trip use cases — add and paginate trip entries.

AddTripUseCase:
  Validates the input command, delegates to TripRepository, emits an audit
  log entry, and invalidates relevant caches.  Raises ValidationError on bad
  input so the caller (route or API) never needs to re-validate.

GetTripsUseCase:
  Thin wrapper around TripRepository.get_page() — exists mainly so routes
  can depend on a stable application-layer interface instead of the
  repository directly, making future changes (e.g. adding authorisation
  checks) transparent to callers.

No Flask imports anywhere in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.exceptions import ValidationError
from backend.helpers import (
    ensure_non_empty_text,
    validate_iso_date,
    validate_odometer_range,
    parse_positive_int_field,
)
from backend.infrastructure.repositories.trips import TripRepository
from backend.infrastructure.repositories.vehicles import VehicleRepository
from backend.services.audit_service import AuditService
from backend.services.cache_service import invalidate_prefix


# ---------------------------------------------------------------------------
# AddTripUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class AddTripCommand:
    """Input DTO for AddTripUseCase.

    All values are accepted as raw strings (as they arrive from form/JSON)
    so that validation lives in the use case, not the route.

    Attributes:
        vehicle_id:      Raw vehicle ID string (e.g. "1").
        date_val:        Trip date in ``YYYY-MM-DD`` format.
        driver:          Driver name (non-empty).
        odo_start:       Odometer at start (optional, positive int as string).
        odo_end:         Odometer at end (optional, positive int as string).
        purpose:         Trip purpose / description (non-empty).
        notes:           Optional free-text notes.
        added_by:        Username of the submitter (from session).
        time_start:      Optional HH:MM string.
        time_end:        Optional HH:MM string.
        equipment_used:  List of equipment dicts from the form parser.
    """
    vehicle_id: str
    date_val: str
    driver: str
    odo_start: str | None
    odo_end: str | None
    purpose: str
    notes: str
    added_by: str
    time_start: str | None = None
    time_end: str | None = None
    equipment_used: list[dict] | None = None


class AddTripUseCase:
    """Validate → persist → audit → invalidate cache.

    Usage::

        cmd = AddTripCommand(vehicle_id="1", date_val="2026-05-12", ...)
        trip_id = AddTripUseCase.execute(cmd)

    Raises:
        ValidationError: on any validation failure (bad date, missing field,
                         invalid vehicle, odometer range mismatch).
    """

    def __init__(self, trip_repo: TripRepository, vehicle_repo: VehicleRepository):
        self._trip_repo = trip_repo
        self._vehicle_repo = vehicle_repo

    def execute_instance(self, cmd: AddTripCommand) -> int:
        """Validate the command, write to DB, emit side-effects.

        Returns:
            The new trip's primary key (int).

        Raises:
            ValidationError: if any field fails validation.
        """
        # ── 1. Validate fields ──────────────────────────────────────────
        try:
            trip_date = validate_iso_date(cmd.date_val, 'Data')
            driver = ensure_non_empty_text(cmd.driver, 'Kierowca')
            purpose = ensure_non_empty_text(cmd.purpose, 'Cel wyjazdu')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        try:
            odo_start = parse_positive_int_field(cmd.odo_start, 'Km start')
            odo_end = parse_positive_int_field(cmd.odo_end, 'Km koniec')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        try:
            validate_odometer_range(odo_start, odo_end)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # ── 2. Validate vehicle exists and is active ────────────────────
        vehicle = self._vehicle_repo.get_active(cmd.vehicle_id)
        if not vehicle:
            raise ValidationError('Nieprawidłowy pojazd.')

        # ── 3. Persist ──────────────────────────────────────────────────
        trip_id = self._trip_repo.add(
            vehicle_id=vehicle['id'],
            date_val=trip_date,
            driver=driver,
            odo_start=odo_start,
            odo_end=odo_end,
            purpose=purpose,
            notes=cmd.notes,
            added_by=cmd.added_by,
            time_start=cmd.time_start or None,
            time_end=cmd.time_end or None,
            equipment_used=cmd.equipment_used or None,
        )

        # ── 4. Side effects (best-effort, non-fatal) ────────────────────
        AuditService.log(
            'Dodanie', 'Wyjazd',
            f'Pojazd ID: {vehicle["id"]}, Kierowca: {driver}, Data: {trip_date}',
        )
        try:
            invalidate_prefix(f'report:{vehicle["id"]}:')
            # dashboard and last_km cache are invalidated inside TripRepository.add
        except Exception:
            pass

        return trip_id

    @classmethod
    def execute(cls, cmd: AddTripCommand) -> int:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_add_trip_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# GetTripsUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class GetTripsQuery:
    """Input DTO for GetTripsUseCase.

    All fields are optional; omitting them returns an unfiltered, first-page
    result set.
    """
    vehicle_id: str | int | None = None
    okres: str = ""
    od: str = ""
    do_: str = ""
    page: int = 1


class GetTripsUseCase:
    """Paginate trip entries for the list view.

    Usage::

        q = GetTripsQuery(vehicle_id="1", page=2)
        entries, total, total_pages, page = GetTripsUseCase.execute(q)
    """

    def __init__(self, trip_repo: TripRepository):
        self._trip_repo = trip_repo

    def execute_instance(
        self, query: GetTripsQuery,
    ) -> tuple[list[dict], int, int, int]:
        """Return paginated trip rows.

        Returns:
            Tuple of ``(entries, total_count, total_pages, current_page)``
            matching the signature of ``TripRepository.get_page``.
        """
        return self._trip_repo.get_page(
            vehicle_id=query.vehicle_id,
            okres=query.okres,
            od=query.od,
            do_=query.do_,
            page=query.page,
        )

    @classmethod
    def execute(
        cls, query: GetTripsQuery,
    ) -> tuple[list[dict], int, int, int]:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_trips_use_case()
        return use_case.execute_instance(query)
