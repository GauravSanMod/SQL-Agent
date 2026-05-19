"""
Foreign-key relationship graph.

Builds a lightweight NetworkX graph from the explicit
relationships in the semantic model.  Used by Agent 2
(Schema Selector) to discover join paths between tables
via BFS — deterministic, no LLM needed.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import networkx as nx

from schema.models import RelationshipMeta, UnifiedRegistry

LOGGER = logging.getLogger(__name__)


class SchemaGraph:
    """
    Undirected FK graph over all tables in the registry.

    Nodes = table names.
    Edges = FK relationships, annotated with join metadata.
    """

    def __init__(self, registry: UnifiedRegistry) -> None:
        self._graph = nx.Graph()
        self._build(registry)

    # ── Construction ─────────────────────────────────────

    def _build(self, registry: UnifiedRegistry) -> None:
        """Populate graph from registry relationships."""
        for table in registry.all_tables:
            self._graph.add_node(
                table.name,
                platform=table.platform,
                fqn=table.fully_qualified_name,
            )

        for rel in registry.all_relationships:
            self._graph.add_edge(
                rel.left_table,
                rel.right_table,
                left_column=rel.left_column,
                right_column=rel.right_column,
                join_type=rel.join_type,
                relationship_type=rel.relationship_type,
                name=rel.name,
            )

        LOGGER.info(
            "SchemaGraph built: %d nodes, %d edges",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
        )

    # ── Queries ──────────────────────────────────────────

    def find_join_path(
        self,
        table_a: str,
        table_b: str,
    ) -> Optional[List[str]]:
        """
        Find the shortest join path between two tables.

        Returns:
            Ordered list of table names forming the path,
            or ``None`` if no path exists.
        """
        if table_a not in self._graph:
            LOGGER.warning("Table not in graph: %s", table_a)
            return None
        if table_b not in self._graph:
            LOGGER.warning("Table not in graph: %s", table_b)
            return None
        try:
            return nx.shortest_path(
                self._graph, table_a, table_b,
            )
        except nx.NetworkXNoPath:
            return None

    def find_join_paths_for_tables(
        self,
        tables: List[str],
    ) -> List[str]:
        """
        Given a set of tables, find the minimal spanning
        subgraph that connects them all (Steiner-tree
        approximation via pairwise shortest paths).

        Returns:
            Ordered list of ALL tables needed (including
            intermediate ones the user didn't mention).
        """
        if len(tables) <= 1:
            return tables

        all_nodes: set = set()
        for i in range(len(tables)):
            for j in range(i + 1, len(tables)):
                path = self.find_join_path(
                    tables[i], tables[j],
                )
                if path:
                    all_nodes.update(path)

        return list(all_nodes) if all_nodes else tables

    def get_join_condition(
        self,
        table_a: str,
        table_b: str,
    ) -> Optional[Dict[str, str]]:
        """
        Get the join condition between two directly
        connected tables.

        Returns:
            Dict with keys: left_column, right_column,
            join_type, relationship_type.
        """
        if not self._graph.has_edge(table_a, table_b):
            return None
        return dict(self._graph[table_a][table_b])

    def get_all_join_conditions(
        self,
        table_path: List[str],
    ) -> List[Dict[str, str]]:
        """
        For an ordered path of tables, return the join
        condition for each consecutive pair.
        """
        conditions: List[Dict[str, str]] = []
        for i in range(len(table_path) - 1):
            cond = self.get_join_condition(
                table_path[i], table_path[i + 1],
            )
            if cond:
                cond["left_table"] = table_path[i]
                cond["right_table"] = table_path[i + 1]
                conditions.append(cond)
        return conditions

    def get_neighbours(self, table: str) -> List[str]:
        """Direct neighbours of a table in the FK graph."""
        if table in self._graph:
            return list(self._graph.neighbors(table))
        return []

    @property
    def tables(self) -> List[str]:
        """All table names in the graph."""
        return list(self._graph.nodes)
