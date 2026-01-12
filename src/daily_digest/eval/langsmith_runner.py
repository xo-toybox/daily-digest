"""LangSmith-native evaluation runner using evaluate_existing().

Results appear directly in LangSmith dashboard.

Usage:
    # Evaluate a LangSmith experiment
    results = run_langsmith_eval("my-experiment", include_trajectory=True)

    # Evaluate recent runs from a project
    results = evaluate_recent_runs(limit=10, include_trajectory=True)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

from .langsmith_evaluators import (
    CODE_EVALUATORS,
    OUTPUT_EVALUATORS,
    TRAJECTORY_EVALUATORS,
)

if TYPE_CHECKING:
    from langsmith import Client


def _get_langsmith_client() -> "Client":
    """Get LangSmith client. Raises if not configured."""
    from langsmith import Client

    return Client()


def run_langsmith_eval(
    experiment_name: str,
    evaluators: Sequence[Callable] | None = None,
    include_trajectory: bool = False,
    include_model_based: bool = False,
    max_concurrency: int = 4,
) -> dict:
    """Run evaluators on an existing LangSmith experiment.

    Results appear in LangSmith dashboard under the experiment.

    Args:
        experiment_name: Name or ID of the experiment to evaluate
        evaluators: Custom evaluators (defaults to CODE_EVALUATORS)
        include_trajectory: Include trajectory evaluators from agentevals
        include_model_based: Include model-based output evaluators
        max_concurrency: Parallel evaluation workers

    Returns:
        Evaluation results summary
    """
    from langsmith.evaluation import evaluate_existing

    if evaluators is None:
        evaluators = list(CODE_EVALUATORS)
        if include_model_based:
            evaluators.extend(OUTPUT_EVALUATORS)
        if include_trajectory:
            evaluators.extend(TRAJECTORY_EVALUATORS)

    # Run evaluation - results appear in LangSmith dashboard
    results = evaluate_existing(
        experiment=experiment_name,
        evaluators=evaluators,
        max_concurrency=max_concurrency,
        load_nested=True,  # Critical: enables access to child_runs for tool calls
    )

    return {
        "experiment": experiment_name,
        "evaluators_run": len(evaluators),
        "results": results,
    }


async def run_langsmith_eval_async(
    experiment_name: str,
    evaluators: Sequence[Callable] | None = None,
    include_trajectory: bool = False,
    include_model_based: bool = False,
    max_concurrency: int = 4,
) -> dict:
    """Async version of run_langsmith_eval.

    Args:
        experiment_name: Name or ID of the experiment to evaluate
        evaluators: Custom evaluators (defaults to CODE_EVALUATORS)
        include_trajectory: Include trajectory evaluators from agentevals
        include_model_based: Include model-based output evaluators
        max_concurrency: Parallel evaluation workers

    Returns:
        Evaluation results summary
    """
    from langsmith.evaluation import aevaluate_existing

    if evaluators is None:
        evaluators = list(CODE_EVALUATORS)
        if include_model_based:
            evaluators.extend(OUTPUT_EVALUATORS)
        if include_trajectory:
            evaluators.extend(TRAJECTORY_EVALUATORS)

    results = await aevaluate_existing(
        experiment=experiment_name,
        evaluators=evaluators,
        max_concurrency=max_concurrency,
        load_nested=True,
    )

    return {
        "experiment": experiment_name,
        "evaluators_run": len(evaluators),
        "results": results,
    }


def evaluate_recent_runs(
    project_name: str = "daily-digest",
    limit: int = 10,
    evaluators: Sequence[Callable] | None = None,
    include_trajectory: bool = False,
    include_model_based: bool = False,
) -> list[dict]:
    """Evaluate recent runs from a project.

    Alternative to evaluate_existing when you don't have an experiment name.
    Evaluates individual runs and returns results directly (not via dashboard).

    Args:
        project_name: LangSmith project name
        limit: Number of recent runs to evaluate
        evaluators: Custom evaluators (defaults to CODE_EVALUATORS)
        include_trajectory: Include trajectory evaluators from agentevals
        include_model_based: Include model-based output evaluators

    Returns:
        List of evaluation results per run
    """
    if evaluators is None:
        evaluators = list(CODE_EVALUATORS)
        if include_model_based:
            evaluators.extend(OUTPUT_EVALUATORS)
        if include_trajectory:
            evaluators.extend(TRAJECTORY_EVALUATORS)

    client = _get_langsmith_client()

    # Get recent runs - filter for actual expand_item/LangGraph runs, not evaluator runs
    # Use is_root=true and name matching to avoid picking up child runs or evaluator runs
    runs = list(
        client.list_runs(
            project_name=project_name,
            limit=limit,
            filter='and(eq(is_root, true), or(eq(name, "LangGraph"), eq(name, "expand_item")))',
        )
    )

    results = []
    for run in runs:
        # Fetch full run with nested children for trajectory evaluators
        full_run = client.read_run(run.id, load_child_runs=True)

        run_results = {
            "run_id": str(run.id),
            "name": run.name,
            "evaluations": {},
        }

        for evaluator in evaluators:
            try:
                eval_result = evaluator(full_run, None)
                key = eval_result.get("metric_name", eval_result.get("key", evaluator.__name__))
                run_results["evaluations"][key] = eval_result
            except Exception as e:
                run_results["evaluations"][evaluator.__name__] = {"error": str(e)}

        # Compute aggregate score
        scores = [
            r.get("score")
            for r in run_results["evaluations"].values()
            if r.get("score") is not None
        ]
        if scores:
            run_results["aggregate_score"] = sum(scores) / len(scores)

        results.append(run_results)

    return results


def format_recent_eval_results(results: list[dict]) -> str:
    """Format evaluate_recent_runs output for display."""
    lines = []

    for run_result in results:
        lines.append(f"\n[Run: {run_result['run_id'][:8]}...]")
        if run_result.get("name"):
            lines.append(f"  Name: {run_result['name']}")

        for key, eval_data in run_result["evaluations"].items():
            if "error" in eval_data:
                lines.append(f"  {key}: ERROR - {eval_data['error']}")
            else:
                score = eval_data.get("score")
                score_str = f"{score:.2f}" if score is not None else "N/A"
                passed = eval_data.get("pass")
                status = ""
                if passed is True:
                    status = " [PASS]"
                elif passed is False:
                    status = " [FAIL]"
                lines.append(f"  {key}: {score_str}{status}")

        if "aggregate_score" in run_result:
            lines.append(f"  Aggregate: {run_result['aggregate_score']:.2f}")

    return "\n".join(lines)
