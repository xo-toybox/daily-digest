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
from .seed_collector import (
    validate_url,
    score_seed_quality,
    list_categories,
    get_category_info,
    export_seeds_to_jsonl,
    TOPIC_CATEGORIES,
)
from .langsmith_evaluators import (
    # LangSmith-compatible evaluators
    structure_evaluator_ls,
    efficiency_evaluator_ls,
    sources_retrieved_evaluator_ls,
    groundedness_evaluator_ls,
    coverage_evaluator_ls,
    authority_evaluator_ls,
    topic_evaluator_ls,
    # Trajectory evaluators
    trajectory_tool_efficiency,
    trajectory_reasoning_quality,
    trajectory_goal_completion,
    # Evaluator collections
    CODE_EVALUATORS,
    OUTPUT_EVALUATORS,
    TRAJECTORY_EVALUATORS,
    ALL_EVALUATORS,
)
from .langsmith_runner import (
    run_langsmith_eval,
    run_langsmith_eval_async,
    evaluate_recent_runs,
    format_recent_eval_results,
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
    # Seed collection
    "validate_url",
    "score_seed_quality",
    "list_categories",
    "get_category_info",
    "export_seeds_to_jsonl",
    "TOPIC_CATEGORIES",
    # LangSmith-native evaluators
    "structure_evaluator_ls",
    "efficiency_evaluator_ls",
    "sources_retrieved_evaluator_ls",
    "groundedness_evaluator_ls",
    "coverage_evaluator_ls",
    "authority_evaluator_ls",
    "topic_evaluator_ls",
    "trajectory_tool_efficiency",
    "trajectory_reasoning_quality",
    "trajectory_goal_completion",
    "CODE_EVALUATORS",
    "OUTPUT_EVALUATORS",
    "TRAJECTORY_EVALUATORS",
    "ALL_EVALUATORS",
    # LangSmith runner
    "run_langsmith_eval",
    "run_langsmith_eval_async",
    "evaluate_recent_runs",
    "format_recent_eval_results",
]
