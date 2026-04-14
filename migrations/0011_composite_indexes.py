from yoyo import step

steps = [
    step(
        '''
        CREATE INDEX IF NOT EXISTS idx_fuel_vehicle_date
            ON fuel (vehicle_id, date);

        CREATE INDEX IF NOT EXISTS idx_maintenance_vehicle_date
            ON maintenance (vehicle_id, date);

        CREATE INDEX IF NOT EXISTS idx_trips_date_created_desc
            ON trips (date DESC, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_fuel_date_created_desc
            ON fuel (date DESC, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_maintenance_due_date_pending
            ON maintenance (due_date)
            WHERE status = 'pending';
        ''',
        '''
        DROP INDEX IF EXISTS idx_maintenance_due_date_pending;
        DROP INDEX IF EXISTS idx_fuel_date_created_desc;
        DROP INDEX IF EXISTS idx_trips_date_created_desc;
        DROP INDEX IF EXISTS idx_maintenance_vehicle_date;
        DROP INDEX IF EXISTS idx_fuel_vehicle_date;
        ''',
    )
]
