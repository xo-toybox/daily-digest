"""Dataset management for LangSmith evaluation datasets.

Utilities for building and managing golden datasets from production traces.
"""

import json
from pathlib import Path
from typing import Any

from ..models import Expansion


def get_langsmith_client():
    """Get LangSmith client, or None if not configured."""
    try:
        from langsmith import Client

        return Client()
    except ImportError:
        return None
    except Exception:
        return None


def create_dataset(name: str, description: str = "") -> bool:
    """Create a new LangSmith dataset.

    Args:
        name: Dataset name
        description: Dataset description

    Returns:
        True if created successfully
    """
    client = get_langsmith_client()
    if not client:
        return False

    try:
        client.create_dataset(name, description=description)
        return True
    except Exception:
        return False


def list_datasets() -> list[dict]:
    """List all available datasets."""
    client = get_langsmith_client()
    if not client:
        return []

    try:
        datasets = list(client.list_datasets())
        return [
            {
                "name": d.name,
                "description": d.description,
                "example_count": d.example_count,
                "created_at": str(d.created_at),
            }
            for d in datasets
        ]
    except Exception:
        return []


def add_expansion_to_dataset(
    dataset_name: str,
    expansion: Expansion,
    inputs: dict,
    quality_tier: str = "synthetic",
    metadata: dict | None = None,
) -> bool:
    """Add an expansion example to a dataset.

    Args:
        dataset_name: Target dataset name
        expansion: The expansion to add
        inputs: Original inputs (item_type, content, note)
        quality_tier: One of "synthetic", "silver", "gold"
        metadata: Additional metadata

    Returns:
        True if added successfully
    """
    client = get_langsmith_client()
    if not client:
        return False

    outputs = {
        "source_summary": expansion.source_summary,
        "key_points": expansion.key_points,
        "related": [r.model_dump() for r in expansion.related],
        "topics": expansion.topics,
        "assessment": expansion.assessment,
        "research_notes": expansion.research_notes,
    }

    example_metadata = {
        "quality_tier": quality_tier,
        "item_id": expansion.item_id,
        **(metadata or {}),
    }

    try:
        client.create_example(
            dataset_name=dataset_name,
            inputs=inputs,
            outputs=outputs,
            metadata=example_metadata,
        )
        return True
    except Exception:
        return False


def find_runs_by_quality(
    project_name: str = "daily-digest",
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int = 100,
) -> list[dict]:
    """Find runs filtered by quality score.

    Args:
        project_name: LangSmith project name
        min_score: Minimum quality score (inclusive)
        max_score: Maximum quality score (inclusive)
        limit: Maximum runs to return

    Returns:
        List of run summaries
    """
    client = get_langsmith_client()
    if not client:
        return []

    try:
        # Build filter string
        filters = []
        if min_score is not None:
            filters.append(f'gte(feedback_scores["quality"], {min_score})')
        if max_score is not None:
            filters.append(f'lte(feedback_scores["quality"], {max_score})')

        filter_str = " and ".join(filters) if filters else None

        runs = list(
            client.list_runs(
                project_name=project_name,
                filter=filter_str,
                limit=limit,
            )
        )

        return [
            {
                "id": str(run.id),
                "name": run.name,
                "status": run.status,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "feedback_scores": getattr(run, "feedback_stats", {}),
            }
            for run in runs
        ]
    except Exception:
        return []


def export_dataset_to_jsonl(dataset_name: str, output_path: Path) -> int:
    """Export dataset examples to JSONL file.

    Args:
        dataset_name: Dataset to export
        output_path: Output file path

    Returns:
        Number of examples exported
    """
    client = get_langsmith_client()
    if not client:
        return 0

    try:
        examples = list(client.list_examples(dataset_name=dataset_name))

        with output_path.open("w") as f:
            for example in examples:
                record = {
                    "inputs": example.inputs,
                    "outputs": example.outputs,
                    "metadata": example.metadata,
                }
                f.write(json.dumps(record) + "\n")

        return len(examples)
    except Exception:
        return 0


def import_dataset_from_jsonl(dataset_name: str, input_path: Path) -> int:
    """Import examples from JSONL file to dataset.

    Args:
        dataset_name: Target dataset (must exist)
        input_path: Input JSONL file

    Returns:
        Number of examples imported
    """
    client = get_langsmith_client()
    if not client:
        return 0

    count = 0
    try:
        with input_path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                client.create_example(
                    dataset_name=dataset_name,
                    inputs=record.get("inputs", {}),
                    outputs=record.get("outputs", {}),
                    metadata=record.get("metadata", {}),
                )
                count += 1
        return count
    except Exception:
        return count
