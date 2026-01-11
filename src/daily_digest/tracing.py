"""LangSmith tracing utilities for local export and debugging."""

import json
import os
from datetime import datetime
from pathlib import Path

TRACES_DIR = Path("traces")


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"


def get_project_name() -> str:
    """Get the LangSmith project name."""
    return os.environ.get("LANGCHAIN_PROJECT", "daily-digest")


def export_recent_traces(limit: int = 10, output_dir: Path | None = None) -> list[Path]:
    """Export recent traces from LangSmith to local JSON files.

    Requires LANGCHAIN_API_KEY to be set.

    Args:
        limit: Maximum number of traces to export
        output_dir: Directory to write traces (default: traces/)

    Returns:
        List of paths to exported trace files
    """
    try:
        from langsmith import Client
    except ImportError:
        print("langsmith not installed")
        return []

    api_key = os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        print("LANGCHAIN_API_KEY not set - cannot export traces")
        return []

    output_dir = output_dir or TRACES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    client = Client()
    project_name = get_project_name()

    exported = []
    try:
        runs = list(client.list_runs(project_name=project_name, limit=limit))

        for run in runs:
            # Export each run to JSON
            trace_data = {
                "id": str(run.id),
                "name": run.name,
                "run_type": run.run_type,
                "status": run.status,
                "start_time": run.start_time.isoformat() if run.start_time else None,
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "error": run.error,
                "tags": run.tags,
                "metadata": run.extra.get("metadata") if run.extra else None,
            }

            # Use run ID and timestamp for filename
            timestamp = run.start_time.strftime("%Y%m%d_%H%M%S") if run.start_time else "unknown"
            filename = f"{timestamp}_{run.id}.json"
            path = output_dir / filename

            with path.open("w") as f:
                json.dump(trace_data, f, indent=2, default=str)

            exported.append(path)

    except Exception as e:
        print(f"Error exporting traces: {e}")

    return exported


def print_tracing_status() -> None:
    """Print current tracing configuration status."""
    enabled = is_tracing_enabled()
    project = get_project_name()
    api_key = os.environ.get("LANGCHAIN_API_KEY", "")

    print(f"LangSmith Tracing: {'enabled' if enabled else 'disabled'}")
    print(f"Project: {project}")
    print(f"API Key: {'configured' if api_key else 'not set'}")

    if enabled and api_key:
        print(f"Dashboard: https://smith.langchain.com/o/default/projects/p/{project}")
