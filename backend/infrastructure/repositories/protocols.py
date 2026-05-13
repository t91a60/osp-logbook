from __future__ import annotations

from typing import Any, Protocol


class DashboardRepositoryProtocol(Protocol):
    def get_vehicle_cards(self, cur: Any | None = None) -> list[dict[str, Any]]:
        ...

    def get_recent_trips(self, limit: int = 6, cur: Any | None = None) -> list[dict[str, Any]]:
        ...

    def get_recent_fuel(self, limit: int = 4, cur: Any | None = None) -> list[dict[str, Any]]:
        ...

    def get_aggregate_stats(self, cur: Any | None = None) -> dict[str, int]:
        ...


class ReportRepositoryProtocol(Protocol):
    def get_trip_entries(
        self,
        first_day: str,
        last_day: str,
        vid: int = 0,
        cur: Any | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def get_total_km(
        self,
        first_day: str,
        last_day: str,
        vid: int = 0,
        cur: Any | None = None,
    ) -> int:
        ...

    def get_trip_summary(
        self,
        first_day: str,
        last_day: str,
        vid: int = 0,
        cur: Any | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def get_fuel_summary(
        self,
        first_day: str,
        last_day: str,
        vid: int = 0,
        cur: Any | None = None,
    ) -> dict[int, dict[str, Any]]:
        ...

    def get_maintenance_summary(
        self,
        first_day: str,
        last_day: str,
        vid: int = 0,
        cur: Any | None = None,
    ) -> dict[int, dict[str, Any]]:
        ...


class TripRepositoryProtocol(Protocol):
    def add(
        self,
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
    ) -> int:
        ...

    def get_page(
        self,
        *,
        vehicle_id: str | int | None = None,
        okres: str = "",
        od: str = "",
        do_: str = "",
        page: int = 1,
    ) -> tuple[list[dict], int, int, int]:
        ...

    def get_by_id(self, trip_id: int | str) -> dict | None:
        ...

    def delete(
        self,
        trip_id: int | str,
        requester: str,
        *,
        is_admin: bool = False,
    ) -> None:
        ...


class VehicleRepositoryProtocol(Protocol):
    def get_all(self) -> list[dict]:
        ...

    def get_active(self, vehicle_id: str | int | None) -> dict | None:
        ...

    def get_by_id(self, vid: int) -> dict | None:
        ...

    def get_last_km(self, vid: int) -> tuple[int | None, str | None]:
        ...

    def get_recent_drivers(self, days: int = 90) -> list[str]:
        ...

    def add(self, name: str, plate: str, type_: str) -> None:
        ...

    def update(self, vid: int, name: str, plate: str, type_: str) -> None:
        ...

    def delete(self, vid: int) -> None:
        ...

    def has_linked_rows(self, vid: int) -> bool:
        ...


class FuelRepositoryProtocol(Protocol):
    def add(
        self,
        vehicle_id: int | str | None,
        date_val: str,
        driver: str,
        odometer: int | str | None,
        liters: float | str | None,
        cost: float | str | None,
        notes: str,
        added_by: str,
    ) -> None:
        ...

    def get_by_id(self, entry_id: int | str) -> dict | None:
        ...

    def update(
        self,
        entry_id: int | str,
        vehicle_id: int | str | None,
        date_val: str,
        driver: str,
        odometer: int | str | None,
        liters: float | str | None,
        cost: float | str | None,
        notes: str,
    ) -> None:
        ...

    def delete(
        self,
        entry_id: int | str,
        requester: str,
        *,
        is_admin: bool = False,
    ) -> None:
        ...

    def get_page(
        self,
        *,
        vehicle_id: str | int | None = None,
        okres: str = "",
        od: str = "",
        do_: str = "",
        page: int = 1,
    ) -> tuple[list[dict], int, int, int]:
        ...


class MaintenanceRepositoryProtocol(Protocol):
    def add(
        self,
        vehicle_id: int | str | None,
        date_val: str,
        odometer: int | str | None,
        description: str,
        cost: float | str | None,
        notes: str,
        added_by: str,
        status: str,
        priority: str,
        due_date: str | None,
    ) -> None:
        ...

    def get_by_id(self, entry_id: int | str) -> dict | None:
        ...

    def update(
        self,
        entry_id: int | str,
        vehicle_id: int | str | None,
        date_val: str,
        odometer: int | str | None,
        description: str,
        cost: float | str | None,
        notes: str,
        status: str,
        priority: str,
        due_date: str | None,
    ) -> None:
        ...

    def delete(
        self,
        entry_id: int | str,
        requester: str,
        *,
        is_admin: bool = False,
    ) -> None:
        ...

    def get_page(
        self,
        *,
        vehicle_id: str | int | None = None,
        status_filter: str = "all",
        okres: str = "",
        od: str = "",
        do_: str = "",
        page: int = 1,
    ) -> tuple[list[dict], int, int, int]:
        ...

    def complete(self, entry_id: int | str) -> dict | None:
        ...

    def create_next(self, entry_id: int | str, added_by: str | None = None) -> dict | None:
        ...
