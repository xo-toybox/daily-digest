"""Non-determinism testing with pass@k and pass^k metrics.

pass@k: Does ANY of k runs pass the threshold? (optimistic)
pass^k: Do ALL of k runs pass the threshold? (pessimistic)

High variance between pass@k and pass^k indicates reliability issues.
"""

import asyncio
from typing import Any

from ..models import InboxItem, Expansion
from .runner import run_expansion_eval


async def expand_item_for_eval(
    item: InboxItem,
    expand_fn: Any,
) -> tuple[Expansion, dict]:
    """Run expansion and evaluation together.

    Args:
        item: The inbox item to expand
        expand_fn: The expand_item function to use

    Returns:
        Tuple of (expansion, eval_results)
    """
    expansion = await expand_fn(item)
    eval_results = run_expansion_eval(expansion, include_model_based=False)
    return expansion, eval_results


async def eval_pass_at_k(
    item: InboxItem,
    expand_fn: Any,
    k: int = 3,
    threshold: float = 0.7,
    include_model_based: bool = False,
) -> dict:
    """Run expansion k times and compute pass@k metrics.

    Args:
        item: The inbox item to expand
        expand_fn: The expand_item function (injected to avoid circular import)
        k: Number of runs
        threshold: Score threshold to consider a "pass"
        include_model_based: Whether to run LLM-as-judge evaluators

    Returns:
        Dict with pass@k, pass^k, variance, and individual scores
    """
    scores: list[float] = []
    all_results: list[dict] = []

    for i in range(k):
        expansion = await expand_fn(item)
        eval_results = run_expansion_eval(
            expansion,
            include_model_based=include_model_based,
        )

        # Use aggregate mean score
        mean_score = eval_results.get("_aggregate", {}).get("mean_score")
        if mean_score is not None:
            scores.append(mean_score)
        all_results.append(eval_results)

    if not scores:
        return {
            "pass_at_k": False,
            "pass_k": False,
            "variance": 0.0,
            "scores": [],
            "k": k,
            "threshold": threshold,
            "error": "No valid scores computed",
        }

    return {
        "pass_at_k": max(scores) >= threshold,  # Optimistic: any pass
        "pass_k": min(scores) >= threshold,     # Pessimistic: all pass
        "variance": max(scores) - min(scores),
        "mean": sum(scores) / len(scores),
        "min": min(scores),
        "max": max(scores),
        "scores": scores,
        "k": k,
        "threshold": threshold,
        "reliability": "high" if max(scores) - min(scores) < 0.1 else "low",
    }


def format_pass_at_k_results(results: dict) -> str:
    """Format pass@k results for display."""
    lines = [
        f"  pass@{results['k']}: {'PASS' if results['pass_at_k'] else 'FAIL'}",
        f"  pass^{results['k']}: {'PASS' if results['pass_k'] else 'FAIL'}",
        f"  variance: {results['variance']:.3f} ({results['reliability']} reliability)",
        f"  scores: {', '.join(f'{s:.2f}' for s in results['scores'])}",
    ]
    if results.get("mean") is not None:
        lines.insert(2, f"  mean: {results['mean']:.3f}")
    return "\n".join(lines)
