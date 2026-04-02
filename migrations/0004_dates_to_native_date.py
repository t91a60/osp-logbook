from yoyo import step

steps = [
    step(
        '''
        ALTER TABLE trips
            ALTER COLUMN date TYPE DATE
            USING NULLIF(date, '')::date;

        ALTER TABLE fuel
            ALTER COLUMN date TYPE DATE
            USING NULLIF(date, '')::date;

        ALTER TABLE maintenance
            ALTER COLUMN date TYPE DATE
            USING NULLIF(date, '')::date,
            ALTER COLUMN due_date TYPE DATE
            USING NULLIF(due_date, '')::date;
        ''',
        '''
        ALTER TABLE trips
            ALTER COLUMN date TYPE TEXT
            USING to_char(date, 'YYYY-MM-DD');

        ALTER TABLE fuel
            ALTER COLUMN date TYPE TEXT
            USING to_char(date, 'YYYY-MM-DD');

        ALTER TABLE maintenance
            ALTER COLUMN date TYPE TEXT
            USING to_char(date, 'YYYY-MM-DD'),
            ALTER COLUMN due_date TYPE TEXT
            USING CASE
                WHEN due_date IS NULL THEN NULL
                ELSE to_char(due_date, 'YYYY-MM-DD')
            END;
        ''',
    )
]
