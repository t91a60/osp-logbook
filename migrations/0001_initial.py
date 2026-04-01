from yoyo import step

steps = [
    step('''
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username     TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            display_name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vehicles (
            id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name   TEXT NOT NULL,
            plate  TEXT DEFAULT '',
            type   TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS trips (
            id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            date       TEXT NOT NULL,
            driver     TEXT NOT NULL,
            odo_start  INTEGER,
            odo_end    INTEGER,
            purpose    TEXT NOT NULL,
            notes      TEXT DEFAULT '',
            added_by   TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fuel (
            id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            date       TEXT NOT NULL,
            driver     TEXT NOT NULL,
            odometer   INTEGER,
            liters     REAL NOT NULL,
            cost       REAL,
            notes      TEXT DEFAULT '',
            added_by   TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS maintenance (
            id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            vehicle_id  INTEGER NOT NULL REFERENCES vehicles(id),
            date        TEXT NOT NULL,
            odometer    INTEGER,
            description TEXT NOT NULL,
            cost        REAL,
            notes       TEXT DEFAULT '',
            added_by    TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status      TEXT DEFAULT 'pending',
            priority    TEXT DEFAULT 'medium',
            due_date    TEXT
        );
    ''',
    '''
        DROP TABLE IF EXISTS maintenance;
        DROP TABLE IF EXISTS fuel;
        DROP TABLE IF EXISTS trips;
        DROP TABLE IF EXISTS vehicles;
        DROP TABLE IF EXISTS users;
    ''')
]
