from yoyo import step

steps = [
    step(
        "SELECT 1;  -- baseline: schema applied via schema.sql",
        "SELECT 1;"
    )
]
