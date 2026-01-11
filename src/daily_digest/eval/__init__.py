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
from .runner import (
    run_expansion_eval,
    run_digest_eval,
    format_eval_results,
)
from .pass_at_k import (
    eval_pass_at_k,
    format_pass_at_k_results,
)
from .datasets import (
    create_dataset,
    list_datasets,
    add_expansion_to_dataset,
    find_runs_by_quality,
    export_dataset_to_jsonl,
    import_dataset_from_jsonl,
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
    # Runner
    "run_expansion_eval",
    "run_digest_eval",
    "format_eval_results",
    # Non-determinism testing
    "eval_pass_at_k",
    "format_pass_at_k_results",
    # Dataset management
    "create_dataset",
    "list_datasets",
    "add_expansion_to_dataset",
    "find_runs_by_quality",
    "export_dataset_to_jsonl",
    "import_dataset_from_jsonl",
]
