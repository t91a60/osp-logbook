ALTER TABLE trips ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE maintenance ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_trips_active_date_created_desc
    ON trips (date DESC, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_fuel_active_date_created_desc
    ON fuel (date DESC, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_maintenance_active_date_created_desc
    ON maintenance (date DESC, created_at DESC)
    WHERE deleted_at IS NULL;
