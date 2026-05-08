-- OSP Logbook — full schema for PostgreSQL 17 (Neon.tech)
-- Generated from migrations 0001–0011
-- Import: psql $DATABASE_URL -f schema.sql

CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fast ILIKE search on driver/purpose

CREATE TABLE IF NOT EXISTS users (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    is_admin BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    plate TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS trips (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    driver TEXT NOT NULL,
    odo_start INTEGER,
    odo_end INTEGER,
    purpose TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    added_by TEXT NOT NULL DEFAULT '',
    time_start TEXT,
    time_end TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fuel (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    driver TEXT NOT NULL,
    odometer INTEGER,
    liters REAL NOT NULL,
    cost REAL,
    notes TEXT NOT NULL DEFAULT '',
    added_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    odometer INTEGER,
    description TEXT NOT NULL,
    cost REAL,
    notes TEXT NOT NULL DEFAULT '',
    added_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'medium',
    due_date DATE
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit TEXT NOT NULL DEFAULT 'szt',
    category TEXT NOT NULL DEFAULT 'Pozostałe',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trip_equipment (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    quantity_used INTEGER NOT NULL DEFAULT 1,
    minutes_used INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (trip_id, equipment_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT,
    action TEXT NOT NULL,
    object TEXT NOT NULL,
    details TEXT
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trips_vehicle_odometer ON trips (vehicle_id, odo_end) WHERE odo_end IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fuel_vehicle_odometer ON fuel (vehicle_id, odometer) WHERE odometer IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trips_vehicle_date ON trips (vehicle_id, date);
CREATE INDEX IF NOT EXISTS idx_trips_vehicle_id ON trips (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_trips_date ON trips (date);
CREATE INDEX IF NOT EXISTS idx_fuel_vehicle_id ON fuel (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_fuel_date ON fuel (date);
CREATE INDEX IF NOT EXISTS idx_maint_vehicle_id ON maintenance (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_maint_date ON maintenance (date);
CREATE INDEX IF NOT EXISTS idx_maint_status ON maintenance (status);
CREATE INDEX IF NOT EXISTS idx_equipment_vehicle_id ON equipment (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_trip_equipment_trip_id ON trip_equipment (trip_id);
CREATE INDEX IF NOT EXISTS idx_trip_equipment_equipment_id ON trip_equipment (equipment_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at_desc ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fuel_vehicle_date ON fuel (vehicle_id, date);
CREATE INDEX IF NOT EXISTS idx_maintenance_vehicle_date ON maintenance (vehicle_id, date);
CREATE INDEX IF NOT EXISTS idx_trips_date_created_desc ON trips (date DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fuel_date_created_desc ON fuel (date DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_due_date_pending ON maintenance (due_date) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_trips_purpose_trgm ON trips USING gin(purpose gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_trips_driver_trgm ON trips USING gin(driver gin_trgm_ops);

INSERT INTO schema_version (version) VALUES (10);
-- version 10 = first unified schema, skip yoyo tracking

INSERT INTO users (username, password, display_name, role)
VALUES ('admin', 'CHANGE_ME_RUN_FLASK_INIT', 'Administrator', 'admin')
ON CONFLICT (username) DO NOTHING;
-- Run: flask shell → from backend.db import init_db; init_db()
-- to replace CHANGE_ME with a real bcrypt hash
