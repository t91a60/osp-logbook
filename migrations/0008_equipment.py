from yoyo import step

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            vehicle_id  INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            quantity    INTEGER NOT NULL DEFAULT 1,
            unit        TEXT NOT NULL DEFAULT 'szt',
            category    TEXT NOT NULL DEFAULT 'Pozostałe',
            notes       TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_equipment_vehicle_id ON equipment (vehicle_id);
        """,
        """
        DROP TABLE IF EXISTS equipment CASCADE;
        """
    )
]
