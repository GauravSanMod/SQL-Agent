"""
Agent 4: SQL Validator & Refiner.

Three-layer validation:
 1. Syntax check via sqlglot (zero-cost, no DB).
 2. Schema check — verify all table/column names exist.
 3. Dry-run execution against dummy SQLite DB.

If any layer fails, the error is fed back to Agent 3
for self-correction (up to MAX_RETRIES).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Set

import sqlglot

from agents.schema_selector import PrunedContext
from db.executor import ExecutionResult, SQLExecutor

LOGGER = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of the validation pipeline."""

    is_valid: bool
    sql: str
    error_message: str = ""
    error_layer: str = ""  # syntax | schema | execution
    execution_result: ExecutionResult | None = None


class SQLValidator:
    """
    Validate generated SQL through multiple layers.
    """

    def __init__(
        self,
        executor: SQLExecutor | None = None,
    ) -> None:
        self._executor = executor or SQLExecutor()

    def validate(
        self,
        sql: str,
        context: PrunedContext,
    ) -> ValidationResult:
        """
        Run the full validation pipeline.

        Args:
            sql: The generated SQL query.
            context: The pruned schema context used
                     for generation.

        Returns:
            A ``ValidationResult``.
        """
        if not sql or not sql.strip():
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error_message="Empty SQL query.",
                error_layer="syntax",
            )

        # Layer 1: Syntax check (sqlglot)
        syntax_err = self._check_syntax(sql)
        if syntax_err:
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error_message=syntax_err,
                error_layer="syntax",
            )

        # Layer 2: Schema check
        schema_err = self._check_schema(sql, context)
        if schema_err:
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error_message=schema_err,
                error_layer="schema",
            )

        # Layer 3: Dry-run execution
        exec_result = self._executor.execute(sql)
        if not exec_result.success:
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error_message=exec_result.error_message,
                error_layer="execution",
                execution_result=exec_result,
            )

        return ValidationResult(
            is_valid=True,
            sql=sql,
            execution_result=exec_result,
        )

    # ── Private helpers ──────────────────────────────────

    @staticmethod
    def _check_syntax(sql: str) -> str:
        """
        Parse SQL with sqlglot.

        Returns error message or empty string.
        """
        try:
            # Use 'sqlite' dialect for broad compatibility
            parsed = sqlglot.parse(sql, read="sqlite")
            if not parsed:
                return "sqlglot returned no AST."
            return ""
        except sqlglot.errors.ParseError as exc:
            return f"Syntax error: {exc}"

    @staticmethod
    def _check_schema(
        sql: str,
        context: PrunedContext,
    ) -> str:
        """
        Verify that all referenced tables/columns exist
        in the pruned context.

        Returns error message or empty string.
        """
        known_tables: Set[str] = {
            t.name.lower() for t in context.tables
        }
        known_columns: Set[str] = set()
        for t in context.tables:
            for c in t.columns:
                known_columns.add(c.name.lower())

        try:
            parsed = sqlglot.parse_one(
                sql, read="sqlite",
            )
        except Exception:
            return ""  # syntax layer already handled

        # Extract table references
        for table in parsed.find_all(sqlglot.exp.Table):
            tname = table.name.lower()
            if tname and tname not in known_tables:
                avail = ", ".join(sorted(known_tables))
                return (
                    f"Unknown table '{tname}'. "
                    f"Available: {avail}"
                )

        # Extract column references
        for col in parsed.find_all(sqlglot.exp.Column):
            cname = col.name.lower()
            if cname == "*":
                continue
            if cname and cname not in known_columns:
                avail = ", ".join(sorted(known_columns))
                return (
                    f"Unknown column '{cname}'. "
                    f"Available: {avail}"
                )

        return ""
