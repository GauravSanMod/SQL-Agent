"""
Agent 2: Schema Selector.

The critical innovation — combines vector retrieval
(semantic match) with deterministic FK graph traversal
(structural completion) to produce a **pruned context**
containing only the tables, columns, and join paths that
the SLM needs.

This reduces the context window by 80-90% compared to
feeding the full YAML.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.intent_classifier import ClassificationResult
from retrieval.synonym_index import SynonymIndex
from retrieval.vector_store import VectorStore
from schema.graph import SchemaGraph
from schema.models import (
    ColumnMeta,
    TableMeta,
    UnifiedRegistry,
    VerifiedQuery,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class PrunedColumn:
    """Minimal column info for the SLM prompt."""

    name: str
    data_type: str
    description: str
    role: str


@dataclass
class PrunedTable:
    """Minimal table info for the SLM prompt."""

    name: str
    platform: str
    fqn: str
    columns: List[PrunedColumn] = field(
        default_factory=list,
    )


@dataclass
class JoinCondition:
    """A single join between two tables."""

    left_table: str
    right_table: str
    left_column: str
    right_column: str
    join_type: str


@dataclass
class PrunedContext:
    """
    The complete, minimal context sent to Agent 3 (SLM).

    Contains only what the SLM needs — nothing more.
    """

    tables: List[PrunedTable] = field(
        default_factory=list,
    )
    joins: List[JoinCondition] = field(
        default_factory=list,
    )
    few_shot_examples: List[VerifiedQuery] = field(
        default_factory=list,
    )
    dialect: str = "sqlite"


class SchemaSelector:
    """
    Select and prune the schema for the SLM.

    Pipeline:
        1. Collect candidate columns from classifier
           output + vector search.
        2. Identify the set of required tables.
        3. Use the FK graph to find join paths (including
           intermediate tables).
        4. Prune columns: keep only relevant ones + PKs/FKs.
        5. Attach matching few-shot examples.
    """

    def __init__(
        self,
        registry: UnifiedRegistry,
        graph: SchemaGraph,
        vector_store: VectorStore,
        synonym_index: SynonymIndex,
    ) -> None:
        self._registry = registry
        self._graph = graph
        self._vs = vector_store
        self._syn = synonym_index

    def select(
        self,
        query: str,
        classification: ClassificationResult,
        top_k: int = 15,
    ) -> PrunedContext:
        """
        Build the pruned context for a user query.

        Args:
            query: The user's natural-language question.
            classification: Output from Agent 1.
            top_k: Number of columns to retrieve.

        Returns:
            A ``PrunedContext`` ready for the SLM prompt.
        """
        # Step 1: Gather candidate columns
        candidates = self._gather_candidates(
            query, classification, top_k,
        )

        # Step 2: Identify required tables
        table_names = {
            table for table, _ in candidates
        }

        # Step 3: Graph traversal → fill in join paths
        all_tables = self._graph.find_join_paths_for_tables(
            list(table_names),
        )
        table_names.update(all_tables)

        # Step 4: Build pruned tables with relevant columns
        pruned_tables = self._build_pruned_tables(
            table_names, candidates,
        )

        # Step 5: Extract join conditions
        joins = self._extract_joins(list(table_names))

        # Step 6: Find matching few-shot examples
        examples = self._find_few_shot_examples(query)

        # Step 7: Determine dialect
        dialect = self._resolve_dialect(
            classification.platforms,
        )

        ctx = PrunedContext(
            tables=pruned_tables,
            joins=joins,
            few_shot_examples=examples,
            dialect=dialect,
        )

        LOGGER.info(
            "PrunedContext: %d tables, %d joins, "
            "%d examples, dialect=%s",
            len(ctx.tables),
            len(ctx.joins),
            len(ctx.few_shot_examples),
            ctx.dialect,
        )
        return ctx

    # ── Private helpers ──────────────────────────────────

    def _gather_candidates(
        self,
        query: str,
        classification: ClassificationResult,
        top_k: int,
    ) -> List[Tuple[str, str]]:
        """
        Merge column candidates from synonym index
        and vector search, deduplicating.
        """
        seen: Set[Tuple[str, str]] = set()
        results: List[Tuple[str, str]] = []

        # From classification (synonym hits)
        for pair in classification.mentioned_columns:
            if pair not in seen:
                seen.add(pair)
                results.append(pair)

        # From vector search (broader semantic match)
        vs_hits = self._vs.search(query, top_k=top_k)
        for hit in vs_hits:
            pair = (hit["table"], hit["column"])
            if pair not in seen:
                seen.add(pair)
                results.append(pair)

        return results

    def _build_pruned_tables(
        self,
        table_names: Set[str],
        candidates: List[Tuple[str, str]],
    ) -> List[PrunedTable]:
        """
        Build pruned table objects.

        Includes:
            - All candidate columns for that table.
            - Primary key columns (always needed).
            - FK columns used in joins (always needed).
        """
        # Columns requested per table
        requested: Dict[str, Set[str]] = {}
        for tbl, col in candidates:
            requested.setdefault(tbl, set()).add(col)

        pruned: List[PrunedTable] = []
        for tbl_name in sorted(table_names):
            table_obj = self._registry.get_table(tbl_name)
            if not table_obj:
                continue

            # Columns to include
            keep_cols: Set[str] = requested.get(
                tbl_name, set(),
            )
            # Always include PK
            keep_cols.update(table_obj.primary_key)
            # Always include FK columns from relationships
            for rel in self._registry.all_relationships:
                if rel.left_table == tbl_name:
                    keep_cols.add(rel.left_column)
                if rel.right_table == tbl_name:
                    keep_cols.add(rel.right_column)

            cols = [
                PrunedColumn(
                    name=c.name,
                    data_type=c.data_type,
                    description=c.description,
                    role=c.column_role,
                )
                for c in table_obj.columns
                if c.name in keep_cols
            ]

            pruned.append(
                PrunedTable(
                    name=tbl_name,
                    platform=table_obj.platform,
                    fqn=table_obj.fully_qualified_name,
                    columns=cols,
                )
            )

        return pruned

    def _extract_joins(
        self,
        table_names: List[str],
    ) -> List[JoinCondition]:
        """Extract join conditions for all table pairs."""
        joins: List[JoinCondition] = []
        path = self._graph.find_join_paths_for_tables(
            table_names,
        )
        conditions = self._graph.get_all_join_conditions(
            path,
        )
        for cond in conditions:
            joins.append(
                JoinCondition(
                    left_table=cond.get(
                        "left_table", "",
                    ),
                    right_table=cond.get(
                        "right_table", "",
                    ),
                    left_column=cond.get(
                        "left_column", "",
                    ),
                    right_column=cond.get(
                        "right_column", "",
                    ),
                    join_type=cond.get(
                        "join_type", "inner",
                    ),
                )
            )
        return joins

    def _find_few_shot_examples(
        self,
        query: str,
        max_examples: int = 3,
    ) -> List[VerifiedQuery]:
        """
        Find the most relevant verified queries as
        few-shot examples.

        Uses simple keyword overlap scoring.
        """
        query_tokens = set(query.lower().split())
        scored: List[Tuple[float, VerifiedQuery]] = []

        for vq in self._registry.all_verified_queries:
            q_tokens = set(vq.question.lower().split())
            overlap = len(query_tokens & q_tokens)
            total = len(query_tokens | q_tokens)
            score = overlap / total if total else 0
            scored.append((score, vq))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            vq for _, vq in scored[:max_examples]
            if _ > 0
        ]

    @staticmethod
    def _resolve_dialect(
        platforms: List[str],
    ) -> str:
        """
        Determine the SQL dialect.

        For cross-platform queries, default to SQLite
        (our dry-run environment).
        """
        if len(platforms) == 1:
            dialect_map = {
                "databricks": "databricks",
                "snowflake": "snowflake",
                "bigquery": "bigquery",
            }
            return dialect_map.get(
                platforms[0], "sqlite",
            )
        # Cross-platform → use SQLite for dry-run
        return "sqlite"
