def _to_int(value: str | int | None) -> int | None:
    """Convert a value to int, treating None and empty string as None."""
    if value in (None, ''):
        return None
    return int(value)


def _to_float(value: str | float | None) -> float | None:
    """Convert a value to float, treating None and empty string as None."""
    if value in (None, ''):
        return None
    return float(value)


from .fuel import FuelRepository
from .maintenance import MaintenanceRepository
from .trips import TripRepository
from .vehicles import VehicleRepository


__all__ = [
    "FuelRepository",
    "MaintenanceRepository",
    "TripRepository",
    "VehicleRepository",
    "_to_int",
    "_to_float",
]
