from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class CodeConflictError(Exception):
    """Raised when a generated short code already exists."""


class UrlStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS short_urls (
                    code TEXT PRIMARY KEY,
                    destination TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    click_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed_at TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, code: str, destination: str) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO short_urls (code, destination, created_at) VALUES (?, ?, ?)",
                    (code, destination, created_at),
                )
        except sqlite3.IntegrityError as error:
            raise CodeConflictError(code) from error

    def get(self, code: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT code, destination, created_at, click_count, last_accessed_at
                FROM short_urls WHERE code = ?
                """,
                (code,),
            ).fetchone()
        return dict(row) if row is not None else None

    def record_click(self, code: str) -> str | None:
        accessed_at = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE short_urls
                SET click_count = click_count + 1, last_accessed_at = ?
                WHERE code = ?
                """,
                (accessed_at, code),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT destination FROM short_urls WHERE code = ?", (code,)
            ).fetchone()
        return str(row["destination"])
