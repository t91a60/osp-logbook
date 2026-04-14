from yoyo import step

steps = [
    step(
        """
        ALTER TABLE trips ADD COLUMN IF NOT EXISTS time_start TEXT;
        ALTER TABLE trips ADD COLUMN IF NOT EXISTS time_end   TEXT;
        """,
        """
        ALTER TABLE trips DROP COLUMN IF EXISTS time_start;
        ALTER TABLE trips DROP COLUMN IF EXISTS time_end;
        """
    )
]
