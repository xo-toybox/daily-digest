"""Evaluation framework for daily-digest agent."""

from .expansion_evaluators import (
    structure_evaluator,
    efficiency_evaluator,
    sources_retrieved_evaluator,
    groundedness_evaluator,
    coverage_evaluator,
    authority_evaluator,
    topic_evaluator,
)
from .digest_evaluators import (
    connection_evaluator,
    actionability_evaluator,
    synthesis_evaluator,
)

__all__ = [
    # Expansion evaluators
    "structure_evaluator",
    "efficiency_evaluator",
    "sources_retrieved_evaluator",
    "groundedness_evaluator",
    "coverage_evaluator",
    "authority_evaluator",
    "topic_evaluator",
    # Digest evaluators
    "connection_evaluator",
    "actionability_evaluator",
    "synthesis_evaluator",
]
