from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from backend.db import get_cursor, get_db


class BaseRepository:
    _ACTIVE_TABLES = frozenset({'trips', 'fuel', 'maintenance'})
    _SOFT_DELETE_TABLES = frozenset({'trips', 'fuel', 'maintenance'})

    @staticmethod
    def _assert_sql_identifier(name: str) -> str:
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', name):
            raise ValueError('Invalid SQL identifier.')
        return name

    @staticmethod
    def active_where_clause(alias: str | None = None) -> str:
        if alias:
            BaseRepository._assert_sql_identifier(alias)
        prefix = f'{alias}.' if alias else ''
        return f'{prefix}deleted_at IS NULL'

    def get_active(
        self,
        table: str,
        *,
        cur: Any | None = None,
    ) -> list[dict]:
        table = self._assert_sql_identifier(table)
        if table not in self._ACTIVE_TABLES:
            raise ValueError('Table is not allowed for get_active.')

        def _execute(cursor):
            cursor.execute(
                f'SELECT * FROM {table} WHERE {self.active_where_clause()} ORDER BY id DESC',
            )
            return cursor.fetchall()

        return self._run_with_cursor(cur, _execute)

    def soft_delete(
        self,
        table: str,
        row_id: int | str,
        *,
        id_column: str = 'id',
        cur: Any | None = None,
    ) -> int:
        table = self._assert_sql_identifier(table)
        id_column = self._assert_sql_identifier(id_column)
        if table not in self._SOFT_DELETE_TABLES:
            raise ValueError('Table is not allowed for soft_delete.')

        def _execute(cursor):
            cursor.execute(
                f'''
                UPDATE {table}
                SET deleted_at = CURRENT_TIMESTAMP
                WHERE {id_column} = %s
                  AND {self.active_where_clause()}
                ''',
                (row_id,),
            )
            return cursor.rowcount

        return self._run_with_cursor(cur, _execute)

    def _run_with_cursor(
        self,
        provided_cur: Any | None,
        func: Callable[[Any], Any],
        *,
        get_db_fn: Callable[[], Any] = get_db,
        get_cursor_fn: Callable[[Any], Any] = get_cursor,
    ) -> Any:
        if provided_cur is not None:
            return func(provided_cur)

        conn = get_db_fn()
        cur = get_cursor_fn(conn)
        try:
            return func(cur)
        finally:
            cur.close()

    def _run_in_transaction(
        self,
        func: Callable[[Any], Any],
        *,
        get_db_fn: Callable[[], Any] = get_db,
        get_cursor_fn: Callable[[Any], Any] = get_cursor,
    ) -> Any:
        conn = get_db_fn()
        try:
            with get_cursor_fn(conn) as cur:
                result = func(cur)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
