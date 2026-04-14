from yoyo import step

steps = [
    step(
        '''
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at_desc
            ON audit_log (created_at DESC);
        ''',
        '''
        DROP INDEX IF EXISTS idx_audit_log_created_at_desc;
        ''',
    )
]
