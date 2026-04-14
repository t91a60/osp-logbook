from yoyo import step

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS trip_equipment (
            id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            trip_id         INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
            equipment_id    INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
            quantity_used   INTEGER NOT NULL DEFAULT 1,
            minutes_used    INTEGER,
            notes           TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (trip_id, equipment_id)
        );

        CREATE INDEX IF NOT EXISTS idx_trip_equipment_trip_id      ON trip_equipment (trip_id);
        CREATE INDEX IF NOT EXISTS idx_trip_equipment_equipment_id  ON trip_equipment (equipment_id);
        """,
        """
        DROP TABLE IF EXISTS trip_equipment;
        """
    )
]
