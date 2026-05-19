"""
Pydantic data models for the unified semantic schema.

Every YAML semantic model (Databricks, Snowflake, BigQuery)
is parsed into these common structures so the rest of the
pipeline operates on a single, platform-agnostic interface.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ColumnMeta(BaseModel):
    """A single column (dimension, fact, or time dimension)."""

    name: str
    expr: str
    data_type: str
    description: str = ""
    synonyms: List[str] = Field(default_factory=list)
    sample_values: List[str] = Field(default_factory=list)
    default_aggregation: Optional[str] = None
    column_role: str = "dimension"  # dimension | fact | time


class RelationshipMeta(BaseModel):
    """An explicit FK relationship between two tables."""

    name: str = ""
    left_table: str
    right_table: str
    left_column: str
    right_column: str
    join_type: str = "inner"
    relationship_type: str = "many_to_one"


class VerifiedQuery(BaseModel):
    """A gold-standard (question, SQL) pair for few-shot."""

    name: str = ""
    question: str
    sql: str


class TableMeta(BaseModel):
    """A single table with all its metadata."""

    name: str
    description: str = ""
    platform: str = ""        # databricks | snowflake | bigquery
    database: str = ""        # catalog / project_id / database
    schema_name: str = ""     # schema / dataset_id
    primary_key: List[str] = Field(default_factory=list)
    columns: List[ColumnMeta] = Field(default_factory=list)

    @property
    def fully_qualified_name(self) -> str:
        """Return database.schema.table identifier."""
        parts = [
            p for p in [self.database, self.schema_name, self.name]
            if p
        ]
        return ".".join(parts)

    @property
    def column_names(self) -> List[str]:
        """List of all column names."""
        return [c.name for c in self.columns]


class SemanticModel(BaseModel):
    """Top-level container: all tables + relationships + examples."""

    name: str = ""
    platform: str = ""
    tables: List[TableMeta] = Field(default_factory=list)
    relationships: List[RelationshipMeta] = Field(
        default_factory=list,
    )
    verified_queries: List[VerifiedQuery] = Field(
        default_factory=list,
    )


class UnifiedRegistry(BaseModel):
    """
    Global registry holding every table across all platforms.

    This is the single source of truth for the entire pipeline.
    """

    models: List[SemanticModel] = Field(default_factory=list)

    @property
    def all_tables(self) -> List[TableMeta]:
        """Flatten all tables across all models."""
        return [
            table
            for model in self.models
            for table in model.tables
        ]

    @property
    def all_relationships(self) -> List[RelationshipMeta]:
        """Flatten all relationships across all models."""
        return [
            rel
            for model in self.models
            for rel in model.relationships
        ]

    @property
    def all_verified_queries(self) -> List[VerifiedQuery]:
        """Flatten all verified queries across all models."""
        return [
            vq
            for model in self.models
            for vq in model.verified_queries
        ]

    def get_table(self, table_name: str) -> Optional[TableMeta]:
        """Look up a table by name (case-insensitive)."""
        lower = table_name.lower()
        for table in self.all_tables:
            if table.name.lower() == lower:
                return table
        return None

    def get_tables_for_platform(
        self,
        platform: str,
    ) -> List[TableMeta]:
        """All tables belonging to a specific platform."""
        return [
            t for t in self.all_tables
            if t.platform == platform
        ]
