from yoyo import step

steps = [
    step('''
        CREATE TABLE audit_log (
            id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id    INTEGER REFERENCES users(id),
            username   TEXT,
            action     TEXT NOT NULL,
            object     TEXT NOT NULL,
            details    TEXT
        );
        ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
    ''',
    '''
        ALTER TABLE users DROP COLUMN role;
        DROP TABLE audit_log;
    ''')
]
