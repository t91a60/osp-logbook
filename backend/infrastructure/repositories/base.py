from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.db import get_cursor, get_db


class BaseRepository:
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
