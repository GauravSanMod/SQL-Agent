"""
ChromaDB-based vector store for semantic column retrieval.

Embeds every column's description + synonyms so that
Agent 2 can find relevant columns via cosine similarity
against the user's natural-language question.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import CHROMA_DIR, EMBEDDING_MODEL
from schema.models import UnifiedRegistry

LOGGER = logging.getLogger(__name__)


class VectorStore:
    """Thin wrapper around a ChromaDB collection."""

    COLLECTION = "column_metadata"

    def __init__(self) -> None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.Client(
            ChromaSettings(
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=str(CHROMA_DIR),
            ),
        )
        self._collection = (
            self._client.get_or_create_collection(
                name=self.COLLECTION,
                metadata={
                    "hnsw:space": "cosine",
                },
            )
        )

    # ── Indexing ─────────────────────────────────────────

    def index_registry(
        self,
        registry: UnifiedRegistry,
    ) -> None:
        """
        Embed and upsert all column metadata from the
        registry into ChromaDB.

        Each document is a rich text blob:
            Table: <table> | Column: <col> |
            Description: <desc> |
            Synonyms: <syn1>, <syn2>, ...
        """
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for table in registry.all_tables:
            for col in table.columns:
                doc_id = f"{table.name}__{col.name}"
                doc_text = (
                    f"Table: {table.name}. "
                    f"Column: {col.name}. "
                    f"Description: {col.description}. "
                    f"Synonyms: "
                    f"{', '.join(col.synonyms)}. "
                    f"Data type: {col.data_type}. "
                    f"Role: {col.column_role}."
                )
                meta = {
                    "table": table.name,
                    "column": col.name,
                    "platform": table.platform,
                    "data_type": col.data_type,
                    "role": col.column_role,
                }
                ids.append(doc_id)
                documents.append(doc_text)
                metadatas.append(meta)

        if ids:
            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
        LOGGER.info(
            "Indexed %d column vectors into ChromaDB.",
            len(ids),
        )

    # ── Retrieval ────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 15,
        platform_filter: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top-K most relevant columns for a
        natural-language query.

        Args:
            query: The user's question.
            top_k: Number of results.
            platform_filter: Optional platform constraint.

        Returns:
            List of dicts with keys: table, column,
            platform, data_type, role, score.
        """
        where = None
        if platform_filter:
            where = {"platform": platform_filter}

        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )

        hits: List[Dict[str, Any]] = []
        if results and results["metadatas"]:
            metas = results["metadatas"][0]
            distances = results["distances"][0]
            for meta, dist in zip(metas, distances):
                meta["score"] = round(1 - dist, 4)
                hits.append(meta)

        return hits
