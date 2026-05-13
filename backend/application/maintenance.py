"""
Maintenance use cases — add, edit, delete, paginate, complete and clone maintenance entries.

AddMaintenanceUseCase        – validate → persist → audit.
EditMaintenanceUseCase       – ownership check → validate → update → audit.
DeleteMaintenanceUseCase     – permission guard → delete → audit.
GetMaintenanceUseCase        – thin pagination wrapper.
GetMaintenanceByIdUseCase    – fetch single entry by PK.
CompleteMaintenanceUseCase   – mark entry as completed.
CreateNextMaintenanceUseCase – clone entry as new pending one (due +90 days).

No Flask imports anywhere in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.helpers import (
    ensure_non_empty_text,
    validate_iso_date,
    parse_positive_int_field,
)
from backend.infrastructure.repositories.protocols import (
    MaintenanceRepositoryProtocol,
    VehicleRepositoryProtocol,
)
from backend.services.audit_service import AuditService

_VALID_PRIORITIES = frozenset({'low', 'medium', 'high'})
_VALID_STATUSES = frozenset({'pending', 'completed'})


# ---------------------------------------------------------------------------
# AddMaintenanceUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class AddMaintenanceCommand:
    """Input DTO for AddMaintenanceUseCase — all raw strings from form/JSON."""
    vehicle_id: str
    date_val: str
    description: str
    odometer: str | None
    cost: str | None
    notes: str
    added_by: str
    status: str = 'pending'
    priority: str = 'medium'
    due_date: str | None = None


class AddMaintenanceUseCase:
    """Validate → persist → audit maintenance entry.

    Usage (new-style)::

        cmd = AddMaintenanceCommand(vehicle_id="1", ...)
        use_case = UseCaseFactory.get_add_maintenance_use_case()
        use_case.execute_instance(cmd)

    Usage (legacy classmethod)::

        AddMaintenanceUseCase.execute(cmd)
    """

    def __init__(
        self,
        maintenance_repo: MaintenanceRepositoryProtocol,
        vehicle_repo: VehicleRepositoryProtocol,
    ) -> None:
        self._maintenance_repo = maintenance_repo
        self._vehicle_repo = vehicle_repo

    def execute_instance(self, cmd: AddMaintenanceCommand) -> None:
        # ── 1. Validate fields ─────────────────────────────────────────
        try:
            maint_date = validate_iso_date(cmd.date_val, 'Data')
            description = ensure_non_empty_text(cmd.description, 'Opis')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        try:
            odometer = parse_positive_int_field(cmd.odometer, 'Stan km')
            cost = _to_float_field(cmd.cost, 'Koszt')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        priority = cmd.priority if cmd.priority in _VALID_PRIORITIES else 'medium'
        status = cmd.status if cmd.status in _VALID_STATUSES else 'pending'

        # ── 2. Validate vehicle ────────────────────────────────────────
        vehicle = self._vehicle_repo.get_active(cmd.vehicle_id)
        if not vehicle:
            raise ValidationError('Nieprawidłowy pojazd.')

        # ── 3. Persist ─────────────────────────────────────────────────
        self._maintenance_repo.add(
            vehicle_id=vehicle['id'],
            date_val=maint_date,
            odometer=odometer,
            description=description,
            cost=cost,
            notes=cmd.notes,
            added_by=cmd.added_by,
            status=status,
            priority=priority,
            due_date=cmd.due_date or None,
        )

        AuditService.log(
            'Dodanie', 'Serwis',
            f'Pojazd ID: {vehicle["id"]}, Opis: {description}, Data: {maint_date}',
        )

    @classmethod
    def execute(cls, cmd: AddMaintenanceCommand) -> None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_add_maintenance_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# EditMaintenanceUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class EditMaintenanceCommand:
    """Input DTO for EditMaintenanceUseCase."""
    entry_id: int
    vehicle_id: str
    date_val: str
    description: str
    odometer: str | None
    cost: str | None
    notes: str
    requester: str
    status: str = 'pending'
    priority: str = 'medium'
    due_date: str | None = None
    is_admin: bool = False


class EditMaintenanceUseCase:
    """Ownership check → validate → update → audit maintenance entry."""

    def __init__(
        self,
        maintenance_repo: MaintenanceRepositoryProtocol,
        vehicle_repo: VehicleRepositoryProtocol,
    ) -> None:
        self._maintenance_repo = maintenance_repo
        self._vehicle_repo = vehicle_repo

    def execute_instance(self, cmd: EditMaintenanceCommand) -> None:
        # ── 1. Existence & ownership check ────────────────────────────
        entry = self._maintenance_repo.get_by_id(cmd.entry_id)
        if not entry:
            raise NotFoundError('Nie znaleziono wpisu serwisowego.')
        if not cmd.is_admin and entry.get('added_by') != cmd.requester:
            raise ForbiddenError('Brak uprawnień do edycji wpisu serwisowego.')

        # ── 2. Validate fields ─────────────────────────────────────────
        try:
            maint_date = validate_iso_date(cmd.date_val, 'Data')
            description = ensure_non_empty_text(cmd.description, 'Opis')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        try:
            odometer = parse_positive_int_field(cmd.odometer, 'Stan km')
            cost = _to_float_field(cmd.cost, 'Koszt')
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        priority = cmd.priority if cmd.priority in _VALID_PRIORITIES else 'medium'
        status = cmd.status if cmd.status in _VALID_STATUSES else 'pending'

        # ── 3. Validate vehicle ────────────────────────────────────────
        vehicle = self._vehicle_repo.get_active(cmd.vehicle_id)
        if not vehicle:
            raise ValidationError('Nieprawidłowy pojazd.')

        # ── 4. Persist ─────────────────────────────────────────────────
        self._maintenance_repo.update(
            entry_id=cmd.entry_id,
            vehicle_id=vehicle['id'],
            date_val=maint_date,
            odometer=odometer,
            description=description,
            cost=cost,
            notes=cmd.notes,
            status=status,
            priority=priority,
            due_date=cmd.due_date or None,
        )

        AuditService.log(
            'Edycja', 'Serwis',
            f'ID: {cmd.entry_id}, Pojazd: {vehicle["id"]}, Data: {maint_date}',
        )

    @classmethod
    def execute(cls, cmd: EditMaintenanceCommand) -> None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_edit_maintenance_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# DeleteMaintenanceUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class DeleteMaintenanceCommand:
    """Input DTO for DeleteMaintenanceUseCase."""
    entry_id: int
    requester: str
    is_admin: bool = False


class DeleteMaintenanceUseCase:
    """Permission guard → delete → audit maintenance entry."""

    def __init__(self, maintenance_repo: MaintenanceRepositoryProtocol) -> None:
        self._maintenance_repo = maintenance_repo

    def execute_instance(self, cmd: DeleteMaintenanceCommand) -> None:
        self._maintenance_repo.delete(
            cmd.entry_id,
            requester=cmd.requester,
            is_admin=cmd.is_admin,
        )
        AuditService.log('Usunięcie', 'Serwis', f'ID: {cmd.entry_id}')

    @classmethod
    def execute(cls, cmd: DeleteMaintenanceCommand) -> None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_delete_maintenance_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# GetMaintenanceUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class GetMaintenanceQuery:
    """Input DTO for GetMaintenanceUseCase."""
    vehicle_id: str | int | None = None
    status_filter: str = 'all'
    okres: str = ''
    od: str = ''
    do_: str = ''
    page: int = 1


class GetMaintenanceUseCase:
    """Paginate maintenance entries for the list view."""

    def __init__(self, maintenance_repo: MaintenanceRepositoryProtocol) -> None:
        self._maintenance_repo = maintenance_repo

    def execute_instance(
        self, query: GetMaintenanceQuery,
    ) -> tuple[list[dict], int, int, int]:
        return self._maintenance_repo.get_page(
            vehicle_id=query.vehicle_id,
            status_filter=query.status_filter,
            okres=query.okres,
            od=query.od,
            do_=query.do_,
            page=query.page,
        )

    @classmethod
    def execute(
        cls, query: GetMaintenanceQuery,
    ) -> tuple[list[dict], int, int, int]:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_maintenance_list_use_case()
        return use_case.execute_instance(query)


# ---------------------------------------------------------------------------
# GetMaintenanceByIdUseCase
# ---------------------------------------------------------------------------

class GetMaintenanceByIdUseCase:
    """Fetch a single maintenance entry by its primary key."""

    def __init__(self, maintenance_repo: MaintenanceRepositoryProtocol) -> None:
        self._maintenance_repo = maintenance_repo

    def execute_instance(self, entry_id: int) -> dict | None:
        return self._maintenance_repo.get_by_id(entry_id)

    @classmethod
    def execute(cls, entry_id: int) -> dict | None:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_maintenance_by_id_use_case()
        return use_case.execute_instance(entry_id)


# ---------------------------------------------------------------------------
# CompleteMaintenanceUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class CompleteMaintenanceCommand:
    """Input DTO for CompleteMaintenanceUseCase."""
    entry_id: int
    requester: str
    is_admin: bool = False


class CompleteMaintenanceUseCase:
    """Mark a maintenance entry as completed with ownership check."""

    def __init__(self, maintenance_repo: MaintenanceRepositoryProtocol) -> None:
        self._maintenance_repo = maintenance_repo

    def execute_instance(self, cmd: CompleteMaintenanceCommand) -> dict:
        """Mark entry as completed.

        Returns:
            The completed entry row dict.

        Raises:
            NotFoundError:  if entry does not exist.
            ForbiddenError: if requester is neither owner nor admin.
        """
        row = self._maintenance_repo.complete(cmd.entry_id)
        if not row:
            raise NotFoundError('Nie znaleziono wpisu serwisowego.')
        if not cmd.is_admin and row.get('added_by') != cmd.requester:
            raise ForbiddenError('Brak uprawnień.')
        AuditService.log('Zakończenie', 'Serwis', f'ID: {cmd.entry_id}')
        return row

    @classmethod
    def execute(cls, cmd: CompleteMaintenanceCommand) -> dict:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_complete_maintenance_use_case()
        return use_case.execute_instance(cmd)


# ---------------------------------------------------------------------------
# CreateNextMaintenanceUseCase
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class CreateNextMaintenanceCommand:
    """Input DTO for CreateNextMaintenanceUseCase."""
    entry_id: int
    added_by: str
    requester: str
    is_admin: bool = False


class CreateNextMaintenanceUseCase:
    """Clone maintenance entry as a new pending one due 90 days later."""

    def __init__(self, maintenance_repo: MaintenanceRepositoryProtocol) -> None:
        self._maintenance_repo = maintenance_repo

    def execute_instance(self, cmd: CreateNextMaintenanceCommand) -> dict:
        """Clone entry. Returns original row.

        Raises:
            NotFoundError:  if source entry does not exist.
            ForbiddenError: if requester is neither owner nor admin.
        """
        row = self._maintenance_repo.create_next(
            cmd.entry_id, added_by=cmd.added_by
        )
        if not row:
            raise NotFoundError('Nie znaleziono wpisu serwisowego.')
        if not cmd.is_admin and row.get('added_by') != cmd.requester:
            raise ForbiddenError('Brak uprawnień.')
        AuditService.log('Duplikacja', 'Serwis', f'Źródło ID: {cmd.entry_id}')
        return row

    @classmethod
    def execute(cls, cmd: CreateNextMaintenanceCommand) -> dict:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_create_next_maintenance_use_case()
        return use_case.execute_instance(cmd)


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
