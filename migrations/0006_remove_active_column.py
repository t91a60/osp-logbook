from yoyo import step


steps = [
    step(
        "ALTER TABLE vehicles DROP COLUMN IF EXISTS active;",
        "ALTER TABLE vehicles ADD COLUMN active INTEGER DEFAULT 1;"
    )
]