"""
Inverted synonym index for exact-match column lookup.

Complements the vector store: while embeddings handle
fuzzy / semantic matches, the synonym index catches
exact keyword hits that embeddings might rank lower
(e.g., user says "revenue" → ``totalPrice`` has synonym
"total_revenue").
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from schema.models import UnifiedRegistry

LOGGER = logging.getLogger(__name__)


class SynonymIndex:
    """
    Maps every synonym (lowercased) to its
    (table_name, column_name) pairs.
    """

    def __init__(self) -> None:
        # synonym_lower → set of (table, column)
        self._index: Dict[
            str, Set[Tuple[str, str]]
        ] = defaultdict(set)

    def build(self, registry: UnifiedRegistry) -> None:
        """Index all synonyms from every column."""
        count = 0
        for table in registry.all_tables:
            for col in table.columns:
                # Index the column name itself
                self._index[col.name.lower()].add(
                    (table.name, col.name),
                )
                # Index each synonym
                for syn in col.synonyms:
                    self._index[syn.lower()].add(
                        (table.name, col.name),
                    )
                count += len(col.synonyms) + 1

        LOGGER.info(
            "SynonymIndex built: %d entries across "
            "%d unique keys.",
            count,
            len(self._index),
        )

    def lookup(
        self,
        term: str,
    ) -> List[Tuple[str, str]]:
        """
        Exact match lookup for a term.

        Args:
            term: A user-provided keyword or phrase.

        Returns:
            List of (table_name, column_name) matches.
        """
        return list(self._index.get(term.lower(), set()))

    def lookup_tokens(
        self,
        tokens: List[str],
    ) -> List[Tuple[str, str]]:
        """
        Look up multiple tokens (e.g., from a tokenised
        user query) and return the union of all matches.
        """
        results: Set[Tuple[str, str]] = set()
        for token in tokens:
            results.update(
                self._index.get(token.lower(), set()),
            )
            # Also try bigrams: "total revenue" might be
            # a single synonym
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i + 1]}"
            results.update(
                self._index.get(bigram.lower(), set()),
            )
        return list(results)
