from yoyo import step

steps = [
    step(
        """
        CREATE INDEX idx_trips_vehicle_odometer ON trips (vehicle_id, odo_end) WHERE odo_end IS NOT NULL;
        CREATE INDEX idx_fuel_vehicle_odometer ON fuel (vehicle_id, odometer) WHERE odometer IS NOT NULL;
        CREATE INDEX idx_trips_vehicle_date ON trips (vehicle_id, date);
    """,
        """
        DROP INDEX IF EXISTS idx_trips_vehicle_odometer;
        DROP INDEX IF EXISTS idx_fuel_vehicle_odometer;
        DROP INDEX IF EXISTS idx_trips_vehicle_date;
    """,
    )
]
