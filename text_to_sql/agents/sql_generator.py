"""
Agent 3: SQL Generator.

Constructs an optimised prompt from the pruned context
and sends it to the SLM (via OpenAI-compatible API).
"""

from __future__ import annotations

import logging
from typing import List

from openai import OpenAI

from agents.schema_selector import (
    JoinCondition,
    PrunedContext,
    PrunedTable,
)
from config.settings import (
    SLM_API_KEY,
    SLM_BASE_URL,
    SLM_MODEL,
)
from schema.models import VerifiedQuery

LOGGER = logging.getLogger(__name__)

_SYSTEM = (
    "You are an expert SQL generator. Generate a "
    "syntactically correct {dialect} SQL query based "
    "ONLY on the provided schema. Use ONLY listed "
    "tables and columns. Do NOT invent names. Return "
    "ONLY the SQL query ending with a semicolon."
)


class SQLGenerator:
    """Generate SQL from pruned context via SLM."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._client = OpenAI(
            base_url=base_url or SLM_BASE_URL,
            api_key=api_key or SLM_API_KEY,
        )
        self._model = model or SLM_MODEL

    def generate(
        self,
        question: str,
        context: PrunedContext,
    ) -> str:
        """Generate SQL for the user question."""
        prompt = self._build_prompt(question, context)
        system = _SYSTEM.format(dialect=context.dialect)
        return self._call_slm(system, prompt)

    def generate_with_error_feedback(
        self,
        question: str,
        context: PrunedContext,
        previous_sql: str,
        error_message: str,
    ) -> str:
        """Re-generate SQL after validation failure."""
        schema = self._fmt_schema(context)
        prompt = (
            f"{schema}\n\n"
            f"Previous attempt:\n{previous_sql}\n"
            f"Error: {error_message}\n\n"
            f"Fix the SQL for: {question}\nSQL:"
        )
        system = _SYSTEM.format(dialect=context.dialect)
        return self._call_slm(system, prompt)

    # ── Private ──────────────────────────────────────────

    def _call_slm(self, system: str, user: str) -> str:
        """Send prompt to SLM and extract SQL."""
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            raw = resp.choices[0].message.content or ""
            return self._extract_sql(raw)
        except Exception as exc:
            LOGGER.error("SLM call failed: %s", exc)
            return ""

    def _build_prompt(
        self,
        question: str,
        ctx: PrunedContext,
    ) -> str:
        """Build the full user prompt."""
        schema = self._fmt_schema(ctx)
        return (
            f"{schema}\n\n"
            f"Question: {question}\n\n"
            f"Think step by step:\n"
            f"1. Which tables are needed?\n"
            f"2. What columns to SELECT?\n"
            f"3. What JOINs to use?\n"
            f"4. Any WHERE / GROUP BY / ORDER BY?\n\n"
            f"SQL:"
        )

    def _fmt_schema(self, ctx: PrunedContext) -> str:
        """Format pruned context for the prompt."""
        parts: List[str] = ["### Tables ###"]
        for t in ctx.tables:
            cols = ", ".join(
                f"{c.name} ({c.data_type})"
                for c in t.columns
            )
            parts.append(f"Table: {t.name}\n  {cols}")

        parts.append("\n### Joins ###")
        if ctx.joins:
            for j in ctx.joins:
                parts.append(
                    f"{j.left_table}.{j.left_column} = "
                    f"{j.right_table}.{j.right_column} "
                    f"({j.join_type})"
                )
        else:
            parts.append("No joins needed.")

        if ctx.few_shot_examples:
            parts.append("\n### Examples ###")
            for ex in ctx.few_shot_examples:
                parts.append(
                    f"Q: {ex.question}\nSQL: {ex.sql}"
                )

        return "\n".join(parts)

    @staticmethod
    def _extract_sql(raw: str) -> str:
        """Extract clean SQL from SLM output."""
        if "```sql" in raw:
            s = raw.index("```sql") + 6
            e = raw.index("```", s)
            return raw[s:e].strip()
        if "```" in raw:
            s = raw.index("```") + 3
            e = raw.index("```", s)
            return raw[s:e].strip()
        for pfx in ("SQL:", "Answer:", "Query:"):
            if raw.strip().startswith(pfx):
                raw = raw.strip()[len(pfx):]
        cleaned = raw.strip().rstrip(";") + ";"
        return cleaned
