"""Add numeric integrity CHECK constraints for trips/fuel/maintenance."""

from __future__ import annotations

from alembic import op


revision = '20260521_0002'
down_revision = '20260521_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_trips_odo_start_non_negative'
                  AND conrelid = 'trips'::regclass
            ) THEN
                ALTER TABLE trips
                    ADD CONSTRAINT chk_trips_odo_start_non_negative
                    CHECK (odo_start IS NULL OR odo_start >= 0);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_trips_odo_end_non_negative'
                  AND conrelid = 'trips'::regclass
            ) THEN
                ALTER TABLE trips
                    ADD CONSTRAINT chk_trips_odo_end_non_negative
                    CHECK (odo_end IS NULL OR odo_end >= 0);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_trips_odo_range'
                  AND conrelid = 'trips'::regclass
            ) THEN
                ALTER TABLE trips
                    ADD CONSTRAINT chk_trips_odo_range
                    CHECK (odo_start IS NULL OR odo_end IS NULL OR odo_end >= odo_start);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_fuel_odometer_non_negative'
                  AND conrelid = 'fuel'::regclass
            ) THEN
                ALTER TABLE fuel
                    ADD CONSTRAINT chk_fuel_odometer_non_negative
                    CHECK (odometer IS NULL OR odometer >= 0);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_fuel_liters_positive'
                  AND conrelid = 'fuel'::regclass
            ) THEN
                ALTER TABLE fuel
                    ADD CONSTRAINT chk_fuel_liters_positive
                    CHECK (liters > 0);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_fuel_cost_non_negative'
                  AND conrelid = 'fuel'::regclass
            ) THEN
                ALTER TABLE fuel
                    ADD CONSTRAINT chk_fuel_cost_non_negative
                    CHECK (cost IS NULL OR cost >= 0);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_maintenance_odometer_non_negative'
                  AND conrelid = 'maintenance'::regclass
            ) THEN
                ALTER TABLE maintenance
                    ADD CONSTRAINT chk_maintenance_odometer_non_negative
                    CHECK (odometer IS NULL OR odometer >= 0);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_maintenance_cost_non_negative'
                  AND conrelid = 'maintenance'::regclass
            ) THEN
                ALTER TABLE maintenance
                    ADD CONSTRAINT chk_maintenance_cost_non_negative
                    CHECK (cost IS NULL OR cost >= 0);
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE maintenance DROP CONSTRAINT IF EXISTS chk_maintenance_cost_non_negative;
        ALTER TABLE maintenance DROP CONSTRAINT IF EXISTS chk_maintenance_odometer_non_negative;
        ALTER TABLE fuel DROP CONSTRAINT IF EXISTS chk_fuel_cost_non_negative;
        ALTER TABLE fuel DROP CONSTRAINT IF EXISTS chk_fuel_liters_positive;
        ALTER TABLE fuel DROP CONSTRAINT IF EXISTS chk_fuel_odometer_non_negative;
        ALTER TABLE trips DROP CONSTRAINT IF EXISTS chk_trips_odo_range;
        ALTER TABLE trips DROP CONSTRAINT IF EXISTS chk_trips_odo_end_non_negative;
        ALTER TABLE trips DROP CONSTRAINT IF EXISTS chk_trips_odo_start_non_negative;
        """
    )
