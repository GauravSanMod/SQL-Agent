"""
YAML semantic model parser.

Reads each platform's YAML file and normalises it into the
unified Pydantic models defined in ``schema.models``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

from schema.models import (
    ColumnMeta,
    RelationshipMeta,
    SemanticModel,
    TableMeta,
    UnifiedRegistry,
    VerifiedQuery,
)

LOGGER = logging.getLogger(__name__)


# ── Private helpers ──────────────────────────────────────


def _parse_columns(
    raw_list: List[Dict[str, Any]],
    role: str,
) -> List[ColumnMeta]:
    """Convert a list of raw YAML column dicts to models."""
    columns: List[ColumnMeta] = []
    for col in raw_list:
        sample_vals = col.get("sample_values", [])
        # Some YAML files store sample values as non-strings
        sample_vals = [str(v) for v in sample_vals]
        columns.append(
            ColumnMeta(
                name=col.get("name", ""),
                expr=col.get("expr", col.get("name", "")),
                data_type=col.get("data_type", "STRING"),
                description=col.get("description", ""),
                synonyms=col.get("synonyms", []),
                sample_values=sample_vals,
                default_aggregation=col.get(
                    "default_aggregation",
                ),
                column_role=role,
            )
        )
    return columns


def _parse_base_table(
    raw: Dict[str, Any],
    platform: str,
) -> tuple:
    """Extract (database, schema_name) from base_table."""
    if platform == "databricks":
        return (
            raw.get("catalog", ""),
            raw.get("schema", ""),
        )
    if platform == "snowflake":
        return (
            raw.get("database", ""),
            raw.get("schema", ""),
        )
    if platform == "bigquery":
        return (
            raw.get("project_id", ""),
            raw.get("dataset_id", ""),
        )
    return ("", "")


def _parse_relationships(
    raw_list: List[Dict[str, Any]],
) -> List[RelationshipMeta]:
    """Parse YAML relationship blocks."""
    rels: List[RelationshipMeta] = []
    for r in raw_list:
        cols = r.get("relationship_columns", [])
        for pair in cols:
            rels.append(
                RelationshipMeta(
                    name=r.get("name", ""),
                    left_table=r.get("left_table", ""),
                    right_table=r.get("right_table", ""),
                    left_column=pair.get("left_column", ""),
                    right_column=pair.get(
                        "right_column", "",
                    ),
                    join_type=r.get("join_type", "inner"),
                    relationship_type=r.get(
                        "relationship_type", "many_to_one",
                    ),
                )
            )
    return rels


def _parse_verified_queries(
    raw_list: List[Dict[str, Any]],
) -> List[VerifiedQuery]:
    """Parse verified_queries blocks."""
    queries: List[VerifiedQuery] = []
    for vq in raw_list:
        question = vq.get("question", "")
        sql = vq.get("sql", "")
        if question and sql:
            queries.append(
                VerifiedQuery(
                    name=vq.get("name", ""),
                    question=question,
                    sql=sql,
                )
            )
    return queries


# ── Public API ───────────────────────────────────────────


def parse_yaml(
    path: Path,
    platform: str,
) -> SemanticModel:
    """
    Parse a single YAML semantic model file.

    Args:
        path: Absolute path to the YAML file.
        platform: One of 'databricks', 'snowflake',
                  'bigquery'.

    Returns:
        A fully populated ``SemanticModel``.
    """
    LOGGER.info("Parsing %s (%s)", path.name, platform)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    # Databricks wraps everything under 'semantic_model'
    if "semantic_model" in raw:
        raw = raw["semantic_model"]

    model_name = raw.get("name", path.stem)
    tables: List[TableMeta] = []

    for tbl in raw.get("tables", []):
        base = tbl.get("base_table", {})
        db_name, schema_name = _parse_base_table(
            base, platform,
        )

        dims = _parse_columns(
            tbl.get("dimensions", []), "dimension",
        )
        facts = _parse_columns(
            tbl.get("facts", []), "fact",
        )
        time_dims = _parse_columns(
            tbl.get("time_dimensions", []), "time",
        )

        pk_raw = tbl.get("primary_key", {})
        pk_cols = pk_raw.get("columns", []) if pk_raw else []

        tables.append(
            TableMeta(
                name=tbl.get("name", ""),
                description=tbl.get("description", ""),
                platform=platform,
                database=db_name,
                schema_name=schema_name,
                primary_key=pk_cols,
                columns=dims + facts + time_dims,
            )
        )

    rels = _parse_relationships(
        raw.get("relationships", []),
    )
    vqs = _parse_verified_queries(
        raw.get("verified_queries", []),
    )

    return SemanticModel(
        name=model_name,
        platform=platform,
        tables=tables,
        relationships=rels,
        verified_queries=vqs,
    )


def build_registry(schema_dir: Path) -> UnifiedRegistry:
    """
    Parse all known YAML files and build the global registry.

    Args:
        schema_dir: Directory containing the YAML files.

    Returns:
        A ``UnifiedRegistry`` with all platforms loaded.
    """
    from config.settings import SCHEMA_FILES

    models: List[SemanticModel] = []
    for platform, filename in SCHEMA_FILES.items():
        filepath = schema_dir / filename
        if filepath.exists():
            models.append(parse_yaml(filepath, platform))
        else:
            LOGGER.warning(
                "Schema file not found: %s", filepath,
            )

    registry = UnifiedRegistry(models=models)
    LOGGER.info(
        "Registry built: %d tables, %d relationships, "
        "%d verified queries",
        len(registry.all_tables),
        len(registry.all_relationships),
        len(registry.all_verified_queries),
    )
    return registry
