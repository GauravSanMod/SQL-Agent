"""
Pipeline orchestrator.

Wires all four agents into a single end-to-end pipeline:
    User Query → Intent Classifier → Schema Selector
              → SQL Generator → Validator → Result

Includes the self-correction retry loop: if validation
fails, the error is fed back to the SQL Generator up to
``MAX_RETRIES`` times.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.intent_classifier import (
    ClassificationResult,
    IntentClassifier,
)
from agents.schema_selector import PrunedContext, SchemaSelector
from agents.sql_generator import SQLGenerator
from agents.validator import SQLValidator, ValidationResult
from config.settings import MAX_RETRIES
from db.executor import SQLExecutor

LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Final output of the orchestration pipeline."""

    question: str
    sql: str = ""
    is_valid: bool = False
    classification: ClassificationResult | None = None
    pruned_context: PrunedContext | None = None
    validation: ValidationResult | None = None
    attempts: int = 0
    execution_rows: List[Dict[str, Any]] = field(
        default_factory=list,
    )
    execution_columns: List[str] = field(
        default_factory=list,
    )
    error: str = ""


class Orchestrator:
    """
    End-to-end Text-to-SQL pipeline.

    Usage::

        orch = Orchestrator(
            classifier=...,
            selector=...,
            generator=...,
            validator=...,
        )
        result = orch.run("What is total revenue?")
    """

    def __init__(
        self,
        classifier: IntentClassifier,
        selector: SchemaSelector,
        generator: SQLGenerator,
        validator: SQLValidator,
    ) -> None:
        self._classifier = classifier
        self._selector = selector
        self._generator = generator
        self._validator = validator

    def run(self, question: str) -> PipelineResult:
        """
        Execute the full pipeline for a user question.

        Args:
            question: Natural-language query.

        Returns:
            A ``PipelineResult`` with the generated SQL
            and validation info.
        """
        result = PipelineResult(question=question)

        # Step 1: Intent classification
        LOGGER.info("Step 1: Classifying intent...")
        classification = self._classifier.classify(
            question,
        )
        result.classification = classification

        if not classification.mentioned_tables:
            result.error = (
                "Could not identify relevant tables "
                "for the query."
            )
            LOGGER.warning(result.error)
            return result

        # Step 2: Schema selection
        LOGGER.info("Step 2: Selecting schema...")
        context = self._selector.select(
            question, classification,
        )
        result.pruned_context = context

        if not context.tables:
            result.error = (
                "Schema selector returned no tables."
            )
            LOGGER.warning(result.error)
            return result

        # Step 3 + 4: Generate + Validate (with retries)
        sql = ""
        validation: Optional[ValidationResult] = None

        for attempt in range(1, MAX_RETRIES + 2):
            result.attempts = attempt
            LOGGER.info(
                "Step 3: Generating SQL (attempt %d)...",
                attempt,
            )

            if attempt == 1:
                sql = self._generator.generate(
                    question, context,
                )
            else:
                # Self-correction with error feedback
                sql = (
                    self._generator
                    .generate_with_error_feedback(
                        question,
                        context,
                        sql,
                        validation.error_message
                        if validation
                        else "",
                    )
                )

            if not sql:
                result.error = (
                    "SLM returned empty response."
                )
                continue

            LOGGER.info(
                "Step 4: Validating SQL (attempt %d)...",
                attempt,
            )
            validation = self._validator.validate(
                sql, context,
            )
            result.validation = validation
            result.sql = sql

            if validation.is_valid:
                result.is_valid = True
                if validation.execution_result:
                    result.execution_rows = (
                        validation.execution_result.rows
                    )
                    result.execution_columns = (
                        validation.execution_result.columns
                    )
                LOGGER.info(
                    "SQL validated successfully on "
                    "attempt %d.",
                    attempt,
                )
                return result

            LOGGER.warning(
                "Validation failed (attempt %d): [%s] %s",
                attempt,
                validation.error_layer,
                validation.error_message,
            )

        result.error = (
            f"Failed after {result.attempts} attempts. "
            f"Last error: {validation.error_message}"
            if validation
            else "No SQL generated."
        )
        return result
