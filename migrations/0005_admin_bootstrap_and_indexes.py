from yoyo import step

ADMIN_PASSWORD_HASH = 'scrypt:32768:8:1$M3PDOdfDJDwx6eHn$ac4d6186d134c4ec4d6b5ff7d86ac8123de9130be62dd88c402ba6e92cf22263b8083b476eb424e4956d783e2e751e4093c9a6d293505830ad2e467d9f3ad948'

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

        INSERT INTO users (username, password, display_name, is_admin)
        SELECT 'admin', '{ADMIN_PASSWORD_HASH}', 'Administrator', TRUE
        WHERE NOT EXISTS (SELECT 1 FROM users);
        ''',
        '''
        DELETE FROM users
        WHERE username = 'admin'
          AND display_name = 'Administrator'
          AND is_admin = TRUE;
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
