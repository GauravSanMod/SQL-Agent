"""
Agent 1: Intent Classifier & Schema Router.

Lightweight first pass that determines:
 1. Which database platform(s) the query targets.
 2. Query complexity (single-table / multi-table / agg).
 3. Extracted entity mentions (city names, product
    names, etc.) for downstream filtering.

This agent is intentionally rule-based + embedding
similarity — no LLM call needed, keeping latency and
cost near zero.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from retrieval.synonym_index import SynonymIndex
from retrieval.vector_store import VectorStore
from schema.models import UnifiedRegistry

LOGGER = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Output of the intent classifier."""

    platforms: List[str] = field(default_factory=list)
    mentioned_tables: List[str] = field(
        default_factory=list,
    )
    mentioned_columns: List[Tuple[str, str]] = field(
        default_factory=list,
    )
    complexity: str = "simple"  # simple | join | agg
    is_cross_platform: bool = False
    raw_tokens: List[str] = field(default_factory=list)


class IntentClassifier:
    """
    Classify user intent and route to the right schema.

    Strategy:
        1. Tokenise the query.
        2. Run synonym lookup → identify tables/columns.
        3. Run vector search (top-5) → reinforce matches.
        4. Determine platform(s) from matched tables.
        5. Estimate complexity from keyword heuristics.
    """

    _AGG_KEYWORDS: Set[str] = {
        "total", "sum", "average", "avg", "count",
        "max", "min", "mean", "median", "group",
        "aggregate", "per", "by", "each",
    }
    _JOIN_KEYWORDS: Set[str] = {
        "join", "with", "across", "between",
        "combine", "together", "along with",
        "and their", "and the", "related",
    }

    def __init__(
        self,
        registry: UnifiedRegistry,
        vector_store: VectorStore,
        synonym_index: SynonymIndex,
    ) -> None:
        self._registry = registry
        self._vs = vector_store
        self._syn = synonym_index
        self._table_names = {
            t.name.lower(): t
            for t in registry.all_tables
        }

    def classify(
        self,
        query: str,
    ) -> ClassificationResult:
        """
        Classify a natural-language query.

        Args:
            query: The user's question.

        Returns:
            A ``ClassificationResult`` with platform
            routing and complexity info.
        """
        tokens = self._tokenise(query)
        result = ClassificationResult(raw_tokens=tokens)

        # 1. Synonym lookup → direct column matches
        syn_hits = self._syn.lookup_tokens(tokens)
        result.mentioned_columns = syn_hits

        # 2. Check if any token is a table name
        for token in tokens:
            if token.lower() in self._table_names:
                result.mentioned_tables.append(
                    token.lower(),
                )

        # 3. Vector search → top-5 columns
        vs_hits = self._vs.search(query, top_k=5)
        for hit in vs_hits:
            pair = (hit["table"], hit["column"])
            if pair not in result.mentioned_columns:
                result.mentioned_columns.append(pair)

        # 4. Determine platforms
        platforms: Set[str] = set()
        table_set: Set[str] = set()

        for table_name, _ in result.mentioned_columns:
            table_obj = self._registry.get_table(
                table_name,
            )
            if table_obj:
                platforms.add(table_obj.platform)
                table_set.add(table_name)

        result.platforms = sorted(platforms)
        result.mentioned_tables = sorted(table_set)
        result.is_cross_platform = len(platforms) > 1

        # 5. Estimate complexity
        result.complexity = self._estimate_complexity(
            tokens, result,
        )

        LOGGER.info(
            "Classification: platforms=%s, tables=%s, "
            "complexity=%s",
            result.platforms,
            result.mentioned_tables,
            result.complexity,
        )
        return result

    # ── Private helpers ──────────────────────────────────

    @staticmethod
    def _tokenise(query: str) -> List[str]:
        """Basic whitespace + punctuation tokeniser."""
        cleaned = re.sub(r"[^\w\s]", " ", query.lower())
        return [t for t in cleaned.split() if len(t) > 1]

    def _estimate_complexity(
        self,
        tokens: List[str],
        result: ClassificationResult,
    ) -> str:
        """
        Heuristic complexity estimation.

        - 1 table + no agg keywords → simple
        - 1 table + agg keywords → agg
        - 2+ tables → join
        """
        token_set = set(tokens)
        has_agg = bool(token_set & self._AGG_KEYWORDS)
        num_tables = len(result.mentioned_tables)

        if num_tables >= 2 or result.is_cross_platform:
            return "join"
        if has_agg:
            return "agg"
        return "simple"
