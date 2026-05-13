"""
Fuel use cases — add, edit, delete, paginate and fetch fuel entries.

AddFuelUseCase     – validates input, delegates to FuelRepository, emits audit log.
EditFuelUseCase    – validates, finds vehicle, updates record, emits audit log.
DeleteFuelUseCase  – permission check, delete, emit audit log.
GetFuelUseCase     – thin pagination wrapper around FuelRepository.get_page().
GetFuelByIdUseCase – fetch a single fuel entry by PK.

No Flask imports anywhere in this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.helpers import (
    ensure_non_empty_text,
    validate_iso_date,
    parse_positive_int_field,
)
from backend.infrastructure.repositories.protocols import (
    FuelRepositoryProtocol,
    VehicleRepositoryProtocol,
)
from backend.services.audit_service import AuditService


# ---------------------------------------------------------------------------
# AddFuelUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class AddFuelCommand:
    """Input DTO for AddFuelUseCase.

    All values are accepted as raw strings (as they arrive from form/JSON)
    so that validation lives in the use case, not the route.
    """
    vehicle_id: str
    date_val: str
    driver: str
    odometer: str | None
    liters: str | None
    cost: str | None
    notes: str
    added_by: str


class AddFuelUseCase:
    """Validate → persist → audit fuel entry.

    Usage (new-style)::

        cmd = AddFuelCommand(vehicle_id="1", date_val="2026-05-12", ...)
        use_case = UseCaseFactory.get_add_fuel_use_case()
        use_case.execute_instance(cmd)

    Usage (legacy classmethod)::

        AddFuelUseCase.execute(cmd)
    """

    def __init__(
        self,
        fuel_repo: FuelRepositoryProtocol,
        vehicle_repo: VehicleRepositoryProtocol,
    ) -> None:
        self._fuel_repo = fuel_repo
        self._vehicle_repo = vehicle_repo

    def execute_instance(self, cmd: AddFuelCommand) -> None:
        # ── 1. Validate fields ─────────────────────────────────────────
        try:
            fuel_date = validate_iso_date(cmd.date_val, 'Data')
            driver = ensure_non_empty_text(cmd.driver, 'Kierowca')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        try:
            liters = _to_float_field(cmd.liters, 'Litry')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if liters is None:
            raise ValidationError('Podaj ilość paliwa.')

        try:
            cost = _to_float_field(cmd.cost, 'Koszt')
            odometer = parse_positive_int_field(cmd.odometer, 'Stan km')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # ── 2. Validate vehicle ────────────────────────────────────────
        vehicle = self._vehicle_repo.get_active(cmd.vehicle_id)
        if not vehicle:
            raise ValidationError('Nieprawidłowy pojazd.')

        # ── 3. Persist ─────────────────────────────────────────────────
        self._fuel_repo.add(
            vehicle_id=vehicle['id'],
            date_val=fuel_date,
            driver=driver,
            odometer=odometer,
            liters=liters,
            cost=cost,
            notes=cmd.notes,
            added_by=cmd.added_by,
        )

        # ── 4. Side effects ────────────────────────────────────────────
        AuditService.log(
            'Dodanie', 'Tankowanie',
            f'Pojazd ID: {vehicle["id"]}, Litry: {liters}, Data: {fuel_date}',
        )

    @classmethod
    def execute(cls, cmd: AddFuelCommand) -> None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_add_fuel_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# EditFuelUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class EditFuelCommand:
    """Input DTO for EditFuelUseCase."""
    entry_id: int
    vehicle_id: str
    date_val: str
    driver: str
    odometer: str | None
    liters: str | None
    cost: str | None
    notes: str
    requester: str
    is_admin: bool = False


class EditFuelUseCase:
    """Validate → update fuel entry → audit."""

    def __init__(
        self,
        fuel_repo: FuelRepositoryProtocol,
        vehicle_repo: VehicleRepositoryProtocol,
    ) -> None:
        self._fuel_repo = fuel_repo
        self._vehicle_repo = vehicle_repo

    def execute_instance(self, cmd: EditFuelCommand) -> None:
        # ── 1. Existence & ownership check ────────────────────────────
        entry = self._fuel_repo.get_by_id(cmd.entry_id)
        if not entry:
            raise NotFoundError('Nie znaleziono wpisu tankowania.')
        if not cmd.is_admin and entry.get('added_by') != cmd.requester:
            raise ForbiddenError('Brak uprawnień do edycji wpisu tankowania.')

        # ── 2. Validate fields ─────────────────────────────────────────
        try:
            fuel_date = validate_iso_date(cmd.date_val, 'Data')
            driver = ensure_non_empty_text(cmd.driver, 'Kierowca')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        try:
            liters = _to_float_field(cmd.liters, 'Litry')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if liters is None:
            raise ValidationError('Podaj ilość paliwa.')

        try:
            cost = _to_float_field(cmd.cost, 'Koszt')
            odometer = parse_positive_int_field(cmd.odometer, 'Stan km')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # ── 3. Validate vehicle ────────────────────────────────────────
        vehicle = self._vehicle_repo.get_active(cmd.vehicle_id)
        if not vehicle:
            raise ValidationError('Nieprawidłowy pojazd.')

        # ── 4. Persist ─────────────────────────────────────────────────
        self._fuel_repo.update(
            entry_id=cmd.entry_id,
            vehicle_id=vehicle['id'],
            date_val=fuel_date,
            driver=driver,
            odometer=odometer,
            liters=liters,
            cost=cost,
            notes=cmd.notes,
        )

        AuditService.log(
            'Edycja', 'Tankowanie',
            f'ID: {cmd.entry_id}, Pojazd: {vehicle["id"]}, Data: {fuel_date}',
        )

    @classmethod
    def execute(cls, cmd: EditFuelCommand) -> None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_edit_fuel_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# DeleteFuelUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class DeleteFuelCommand:
    """Input DTO for DeleteFuelUseCase."""
    entry_id: int
    requester: str
    is_admin: bool = False


class DeleteFuelUseCase:
    """Delete a fuel entry with permission guard → audit."""

    def __init__(self, fuel_repo: FuelRepositoryProtocol) -> None:
        self._fuel_repo = fuel_repo

    def execute_instance(self, cmd: DeleteFuelCommand) -> None:
        self._fuel_repo.delete(
            cmd.entry_id,
            requester=cmd.requester,
            is_admin=cmd.is_admin,
        )
        AuditService.log('Usunięcie', 'Tankowanie', f'ID: {cmd.entry_id}')

    @classmethod
    def execute(cls, cmd: DeleteFuelCommand) -> None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_delete_fuel_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# GetFuelUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class GetFuelQuery:
    """Input DTO for GetFuelUseCase."""
    vehicle_id: str | int | None = None
    okres: str = ""
    od: str = ""
    do_: str = ""
    page: int = 1


class GetFuelUseCase:
    """Paginate fuel entries for the list view."""

    def __init__(self, fuel_repo: FuelRepositoryProtocol) -> None:
        self._fuel_repo = fuel_repo

    def execute_instance(
        self, query: GetFuelQuery,
    ) -> tuple[list[dict], int, int, int]:
        return self._fuel_repo.get_page(
            vehicle_id=query.vehicle_id,
            okres=query.okres,
            od=query.od,
            do_=query.do_,
            page=query.page,
        )

    @classmethod
    def execute(
        cls, query: GetFuelQuery,
    ) -> tuple[list[dict], int, int, int]:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_fuel_list_use_case()
        return use_case.execute_instance(query)


# ---------------------------------------------------------------------------
# GetFuelByIdUseCase
# ---------------------------------------------------------------------------

class GetFuelByIdUseCase:
    """Fetch a single fuel entry by its primary key."""

    def __init__(self, fuel_repo: FuelRepositoryProtocol) -> None:
        self._fuel_repo = fuel_repo

    def execute_instance(self, entry_id: int) -> dict | None:
        return self._fuel_repo.get_by_id(entry_id)

    @classmethod
    def execute(cls, entry_id: int) -> dict | None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_fuel_by_id_use_case()
        return use_case.execute_instance(entry_id)


# ---------------------------------------------------------------------------
# Internal helpers (no external I/O)
# ---------------------------------------------------------------------------

def _to_float_field(value: str | None, field_name: str) -> float | None:
    """Parse optional float form field; raises ValueError with field name on bad input."""
    if value in (None, ''):
        return None
    try:
        return float(str(value).replace(',', '.'))
    except ValueError:
        raise ValueError(f'{field_name}: nieprawidłowa wartość liczbowa.')
