"""Trajectory logging for agent analysis."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

TRAJECTORIES_DIR = Path("trajectories")


class TrajectoryLogger:
    """Log agent actions and decisions for post-run analysis."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.events: list[dict[str, Any]] = []
        self.start_time = datetime.now()

    def log_item_start(self, item_id: str, content: str, note: str | None) -> None:
        """Log start of item expansion."""
        self.events.append({
            "type": "item_start",
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "content": content,
            "note": note,
        })

    def log_tool_call(self, item_id: str, tool_name: str, tool_input: dict, turn: int) -> None:
        """Log a tool call made by the agent."""
        self.events.append({
            "type": "tool_call",
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "turn": turn,
        })

    def log_tool_result(self, item_id: str, tool_name: str, result_preview: str, turn: int) -> None:
        """Log a tool result."""
        self.events.append({
            "type": "tool_result",
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "tool_name": tool_name,
            "result_preview": result_preview[:500],
            "turn": turn,
        })

    def log_thinking(self, item_id: str, thinking: str, turn: int) -> None:
        """Log agent thinking/reasoning text."""
        self.events.append({
            "type": "thinking",
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "thinking": thinking,
            "turn": turn,
        })

    def log_item_complete(self, item_id: str, expansion_summary: str, topics: list[str], related_count: int, turns_used: int) -> None:
        """Log completion of item expansion."""
        self.events.append({
            "type": "item_complete",
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "expansion_summary": expansion_summary[:300],
            "topics": topics,
            "related_count": related_count,
            "turns_used": turns_used,
        })

    def log_error(self, item_id: str, error: str) -> None:
        """Log an error."""
        self.events.append({
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "error": error,
        })

    def save(self) -> Path:
        """Save trajectory to file."""
        TRAJECTORIES_DIR.mkdir(parents=True, exist_ok=True)
        path = TRAJECTORIES_DIR / f"{self.run_id}.json"

        data = {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "events": self.events,
            "summary": {
                "total_events": len(self.events),
                "items_processed": len([e for e in self.events if e["type"] == "item_complete"]),
                "errors": len([e for e in self.events if e["type"] == "error"]),
                "tool_calls": len([e for e in self.events if e["type"] == "tool_call"]),
            }
        }

        with path.open("w") as f:
            json.dump(data, f, indent=2)

        return path


def load_trajectory(run_id: str) -> dict[str, Any] | None:
    """Load a trajectory by run ID."""
    path = TRAJECTORIES_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def list_trajectories() -> list[str]:
    """List all trajectory run IDs."""
    if not TRAJECTORIES_DIR.exists():
        return []
    return [p.stem for p in TRAJECTORIES_DIR.glob("*.json")]
