from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.db import get_cursor, get_db


class BaseRepository:
    @staticmethod
    def active_where_clause(alias: str | None = None) -> str:
        prefix = f'{alias}.' if alias else ''
        return f'{prefix}deleted_at IS NULL'

    def get_active(
        self,
        table: str,
        *,
        where: str = '',
        params: tuple[Any, ...] = (),
        columns: str = '*',
        order_by: str = 'id DESC',
        cur: Any | None = None,
    ) -> list[dict]:
        def _execute(cursor):
            where_parts = [self.active_where_clause()]
            if where:
                where_parts.append(where)
            cursor.execute(
                f'SELECT {columns} FROM {table} WHERE {" AND ".join(where_parts)} ORDER BY {order_by}',
                params,
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
