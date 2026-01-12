"""Evaluation runner for expansions and digests."""

import json
from pathlib import Path
from typing import Any

from ..models import Expansion
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


def run_expansion_eval(
    expansion: Expansion,
    inputs: dict | None = None,
    run: Any | None = None,
    include_model_based: bool = False,
) -> dict:
    """Run evaluators on a single expansion.

    Args:
        expansion: The expansion to evaluate
        inputs: Original inputs (item_type, content, note)
        run: LangSmith run object (for efficiency evaluator)
        include_model_based: Whether to run LLM-as-judge evaluators (costs API calls)

    Returns:
        Dict with evaluation results keyed by evaluator name
    """
    outputs = {
        "source_summary": expansion.source_summary,
        "key_points": expansion.key_points,
        "related": [r.model_dump() for r in expansion.related],
        "topics": expansion.topics,
        "assessment": expansion.assessment,
        "research_notes": expansion.research_notes,
    }

    inputs = inputs or {}
    results = {}

    # Code-based evaluators (always run)
    results["structure"] = structure_evaluator(inputs, outputs)

    # Trajectory-dependent evaluators (only when run data available)
    # Note: sources_retrieved and efficiency require LangSmith run with child_runs
    if run:
        results["sources_retrieved"] = sources_retrieved_evaluator(run, None)
        results["efficiency"] = efficiency_evaluator(run, None)
    # Skip these evaluators in local mode - they require trajectory data

    # Model-based evaluators (optional, cost API calls)
    if include_model_based:
        results["groundedness"] = groundedness_evaluator(inputs, outputs)
        results["coverage"] = coverage_evaluator(inputs, outputs)
        results["authority"] = authority_evaluator(inputs, outputs)
        results["topic_quality"] = topic_evaluator(inputs, outputs)

    # Compute aggregate score
    scores = [r.get("score") for r in results.values() if r.get("score") is not None]
    results["_aggregate"] = {
        "mean_score": sum(scores) / len(scores) if scores else None,
        "evaluators_run": len(results) - 1,  # Exclude _aggregate itself
        "model_based_included": include_model_based,
    }

    return results


def run_digest_eval(
    digest_outputs: dict,
    expansion_summaries: list[str],
    include_model_based: bool = True,
) -> dict:
    """Run evaluators on a digest.

    Args:
        digest_outputs: Digest data (entries, cross_connections, open_threads)
        expansion_summaries: List of expansion summaries that fed into the digest
        include_model_based: Whether to run LLM-as-judge evaluators

    Returns:
        Dict with evaluation results
    """
    inputs = {
        "expansion_summaries": expansion_summaries,
        "expansion_count": len(expansion_summaries),
    }

    results = {}

    if include_model_based:
        results["connections"] = connection_evaluator(inputs, digest_outputs)
        results["actionability"] = actionability_evaluator(inputs, digest_outputs)
        results["synthesis"] = synthesis_evaluator(inputs, digest_outputs)

    # Compute aggregate
    scores = [r.get("score") for r in results.values() if r.get("score") is not None]
    results["_aggregate"] = {
        "mean_score": sum(scores) / len(scores) if scores else None,
        "evaluators_run": len(results) - 1,
    }

    return results


def evaluate_expansion_file(
    expansion_path: Path,
    include_model_based: bool = False,
) -> dict:
    """Evaluate an expansion from a JSON file.

    Args:
        expansion_path: Path to expansion JSON file
        include_model_based: Whether to run LLM-as-judge evaluators

    Returns:
        Evaluation results
    """
    with expansion_path.open() as f:
        data = json.load(f)

    expansion = Expansion(**data)
    return run_expansion_eval(expansion, include_model_based=include_model_based)


def format_eval_results(results: dict) -> str:
    """Format evaluation results for display."""
    lines = []

    for key, value in results.items():
        if key == "_aggregate":
            continue

        score = value.get("score")
        score_str = f"{score:.2f}" if score is not None else "N/A"

        # Determine pass/fail for code-based
        passed = value.get("pass")
        status = ""
        if passed is True:
            status = " [PASS]"
        elif passed is False:
            status = " [FAIL]"

        lines.append(f"  {key}: {score_str}{status}")

        # Add details for failures
        if value.get("missing_fields"):
            lines.append(f"    missing: {value['missing_fields']}")
        if value.get("error"):
            lines.append(f"    error: {value['error']}")

    # Aggregate
    agg = results.get("_aggregate", {})
    mean = agg.get("mean_score")
    if mean is not None:
        lines.append(f"\n  Aggregate: {mean:.2f}")

    return "\n".join(lines)
