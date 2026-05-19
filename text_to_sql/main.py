"""
Text-to-SQL Multi-Agent Pipeline — Main Entry Point.

Bootstraps all components, builds indices, and exposes
the ``run_query`` function for end-to-end execution.

Usage:
    python main.py

    Then enter natural-language questions interactively.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.intent_classifier import IntentClassifier
from agents.schema_selector import SchemaSelector
from agents.sql_generator import SQLGenerator
from agents.validator import SQLValidator
from config.settings import SCHEMA_DIR, TOP_K_COLUMNS
from db.dummy_data import create_dummy_database
from db.executor import SQLExecutor
from pipeline.orchestrator import Orchestrator, PipelineResult
from retrieval.synonym_index import SynonymIndex
from retrieval.vector_store import VectorStore
from schema.graph import SchemaGraph
from schema.models import UnifiedRegistry, VerifiedQuery
from schema.parser import build_registry
from verified_queries import ALL_VERIFIED

# ── Logging ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger(__name__)
console = Console()


# ── Bootstrap ────────────────────────────────────────────


def bootstrap() -> Orchestrator:
    """
    Initialise all pipeline components and return a
    ready-to-use ``Orchestrator``.
    """
    console.print(
        Panel(
            "[bold cyan]Text-to-SQL Multi-Agent "
            "Pipeline[/bold cyan]\n"
            "Initialising components...",
            title="Startup",
        )
    )

    # 1. Parse schemas
    console.print("  [1/7] Parsing YAML schemas...")
    registry = build_registry(SCHEMA_DIR)

    # 2. Inject verified queries into registry
    console.print("  [2/7] Loading verified queries...")
    _inject_verified_queries(registry)

    # 3. Build FK graph
    console.print("  [3/7] Building FK graph...")
    graph = SchemaGraph(registry)

    # 4. Build vector store
    console.print("  [4/7] Building vector index...")
    vector_store = VectorStore()
    vector_store.index_registry(registry)

    # 5. Build synonym index
    console.print("  [5/7] Building synonym index...")
    synonym_index = SynonymIndex()
    synonym_index.build(registry)

    # 6. Create dummy database
    console.print("  [6/7] Creating dummy database...")
    create_dummy_database()

    # 7. Assemble agents
    console.print("  [7/7] Assembling agents...")
    classifier = IntentClassifier(
        registry, vector_store, synonym_index,
    )
    selector = SchemaSelector(
        registry, graph, vector_store, synonym_index,
    )
    generator = SQLGenerator()
    executor = SQLExecutor()
    validator = SQLValidator(executor)

    orchestrator = Orchestrator(
        classifier=classifier,
        selector=selector,
        generator=generator,
        validator=validator,
    )

    console.print(
        "[bold green]Pipeline ready![/bold green]\n",
    )
    return orchestrator


def _inject_verified_queries(
    registry: UnifiedRegistry,
) -> None:
    """Add all verified queries to the registry models."""
    platform_map = {
        m.platform: m for m in registry.models
    }
    for vq in ALL_VERIFIED:
        # Add to all models (the few-shot selector will
        # pick the most relevant ones anyway)
        for model in registry.models:
            if vq not in model.verified_queries:
                model.verified_queries.append(vq)


# ── Display helpers ──────────────────────────────────────


def display_result(result: PipelineResult) -> None:
    """Pretty-print the pipeline result."""
    if result.is_valid:
        console.print(
            Panel(
                f"[bold green]✅ Valid SQL "
                f"(attempt {result.attempts})"
                f"[/bold green]",
                title="Result",
            )
        )
        console.print(f"\n[bold]SQL:[/bold]")
        console.print(
            Panel(result.sql, title="Generated SQL"),
        )

        if result.execution_rows:
            table = Table(title="Query Results (preview)")
            for col in result.execution_columns:
                table.add_column(col)
            for row in result.execution_rows[:10]:
                table.add_row(
                    *[str(row.get(c, "")) for c in
                      result.execution_columns]
                )
            console.print(table)
    else:
        console.print(
            Panel(
                f"[bold red]❌ Failed[/bold red]\n"
                f"{result.error}",
                title="Error",
            )
        )
        if result.sql:
            console.print(
                f"\n[dim]Last SQL attempt:[/dim]\n"
                f"{result.sql}"
            )

    # Debug info
    if result.classification:
        c = result.classification
        console.print(
            f"\n[dim]Platforms: {c.platforms} | "
            f"Tables: {c.mentioned_tables} | "
            f"Complexity: {c.complexity}[/dim]"
        )


# ── Interactive REPL ─────────────────────────────────────


def main() -> None:
    """Interactive query loop."""
    orch = bootstrap()

    console.print(
        "Enter your questions below. "
        "Type [bold]'quit'[/bold] to exit.\n"
    )

    while True:
        try:
            question = console.input(
                "[bold cyan]Question:[/bold cyan] ",
            )
        except (EOFError, KeyboardInterrupt):
            break

        if question.strip().lower() in (
            "quit", "exit", "q",
        ):
            break

        if not question.strip():
            continue

        result = orch.run(question.strip())
        display_result(result)
        console.print()


if __name__ == "__main__":
    main()
