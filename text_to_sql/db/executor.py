"""
SQL executor for dry-run validation.

Runs generated SQL against the dummy SQLite database
to catch runtime errors (bad column names, type
mismatches, missing tables) before returning the
query to the user.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import DUMMY_DB_PATH

LOGGER = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a SQL dry-run execution."""

    success: bool
    rows: List[Dict[str, Any]] = field(
        default_factory=list,
    )
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    error_message: str = ""


class SQLExecutor:
    """Execute SQL against the dummy SQLite database."""

    def __init__(
        self,
        db_path: Path | None = None,
    ) -> None:
        if db_path is None:
            db_path = DUMMY_DB_PATH
        self._db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Open a read-only connection."""
        conn = sqlite3.connect(
            f"file:{self._db_path}?mode=ro",
            uri=True,
        )
        conn.row_factory = sqlite3.Row
        return conn

    def execute(
        self,
        sql: str,
        limit: int = 10,
    ) -> ExecutionResult:
        """
        Execute SQL and return results.

        A ``LIMIT`` clause is appended if not already
        present — safety measure against full table scans.

        Args:
            sql: The SQL query string.
            limit: Max rows to return.

        Returns:
            An ``ExecutionResult`` with success/error info.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Add LIMIT if not present (safety)
            sql_upper = sql.strip().upper()
            if "LIMIT" not in sql_upper:
                sql = f"{sql.rstrip().rstrip(';')} LIMIT {limit}"

            cursor.execute(sql)
            raw_rows = cursor.fetchall()

            columns = (
                [desc[0] for desc in cursor.description]
                if cursor.description
                else []
            )
            rows = [dict(row) for row in raw_rows]

            conn.close()
            return ExecutionResult(
                success=True,
                rows=rows,
                columns=columns,
                row_count=len(rows),
            )

        except Exception as exc:
            LOGGER.warning("SQL execution failed: %s", exc)
            return ExecutionResult(
                success=False,
                error_message=str(exc),
            )

    def validate_sql(self, sql: str) -> ExecutionResult:
        """
        Validate SQL without returning data.

        Uses EXPLAIN to check the query plan without
        actually fetching rows.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            conn.close()
            return ExecutionResult(success=True)
        except Exception as exc:
            return ExecutionResult(
                success=False,
                error_message=str(exc),
            )
