from yoyo import step

steps = [
    step(
        f'''
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

        CREATE INDEX IF NOT EXISTS idx_trips_vehicle_id ON trips (vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_trips_date ON trips (date);
        CREATE INDEX IF NOT EXISTS idx_fuel_vehicle_id ON fuel (vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_fuel_date ON fuel (date);
        CREATE INDEX IF NOT EXISTS idx_maint_vehicle_id ON maintenance (vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_maint_date ON maintenance (date);
        CREATE INDEX IF NOT EXISTS idx_maint_status ON maintenance (status);
        ''',
        '''
        DROP INDEX IF EXISTS idx_maint_status;
        DROP INDEX IF EXISTS idx_maint_date;
        DROP INDEX IF EXISTS idx_maint_vehicle_id;
        DROP INDEX IF EXISTS idx_fuel_date;
        DROP INDEX IF EXISTS idx_fuel_vehicle_id;
        DROP INDEX IF EXISTS idx_trips_date;
        DROP INDEX IF EXISTS idx_trips_vehicle_id;
        ALTER TABLE users DROP COLUMN IF EXISTS is_admin;
        ''',
    )
]
