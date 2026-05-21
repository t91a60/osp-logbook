"""Add soft-delete columns and active-entry indexes."""

from __future__ import annotations

from alembic import op


revision = '20260521_0003'
down_revision = '20260521_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_maintenance_active_date_created_desc;
        DROP INDEX IF EXISTS idx_fuel_active_date_created_desc;
        DROP INDEX IF EXISTS idx_trips_active_date_created_desc;

        ALTER TABLE maintenance DROP COLUMN IF EXISTS deleted_at;
        ALTER TABLE fuel DROP COLUMN IF EXISTS deleted_at;
        ALTER TABLE trips DROP COLUMN IF EXISTS deleted_at;
        """
    )
