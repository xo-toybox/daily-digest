"""Archive management - store expansions by topic for future reference."""

import json
from pathlib import Path

from .models import Expansion


def get_archive_path(base: Path, topic: str) -> Path:
    """Get archive directory for a topic."""
    # Sanitize topic name for filesystem
    safe_topic = topic.lower().replace(" ", "-").replace("/", "-")
    return base / safe_topic


def archive_expansion(expansion: Expansion, archive_dir: Path) -> list[Path]:
    """
    Archive an expansion under each of its topics.
    Returns list of paths where it was archived.
    """
    if not expansion.topics:
        # Default topic for uncategorized items
        expansion.topics = ["uncategorized"]

    paths = []
    for topic in expansion.topics:
        topic_dir = get_archive_path(archive_dir, topic)
        topic_dir.mkdir(parents=True, exist_ok=True)

        path = topic_dir / f"{expansion.item_id}.json"
        with path.open("w") as f:
            f.write(expansion.model_dump_json(indent=2))
        paths.append(path)

    return paths


def load_topic_expansions(archive_dir: Path, topic: str) -> list[Expansion]:
    """Load all expansions for a topic."""
    topic_dir = get_archive_path(archive_dir, topic)
    if not topic_dir.exists():
        return []

    expansions = []
    for path in topic_dir.glob("*.json"):
        with path.open() as f:
            data = json.load(f)
            expansions.append(Expansion(**data))
    return expansions


def list_topics(archive_dir: Path) -> list[str]:
    """List all topics in the archive."""
    if not archive_dir.exists():
        return []
    return [d.name for d in archive_dir.iterdir() if d.is_dir()]


def find_related_expansions(
    archive_dir: Path, topics: list[str], exclude_ids: set[str] | None = None
) -> list[Expansion]:
    """
    Find archived expansions related to given topics.
    Returns deduplicated list of expansions.
    """
    exclude_ids = exclude_ids or set()
    seen_ids: set[str] = set()
    related: list[Expansion] = []

    for topic in topics:
        for exp in load_topic_expansions(archive_dir, topic):
            if exp.item_id not in exclude_ids and exp.item_id not in seen_ids:
                seen_ids.add(exp.item_id)
                related.append(exp)

    return related


def archive_and_cleanup(
    expansions: list[Expansion],
    expanded_dir: Path,
    archive_dir: Path,
    inbox_path: Path,
) -> None:
    """
    Archive expansions and clean up processed items.
    - Moves expansions to archive under their topics
    - Removes expansion files from expanded/
    - Removes corresponding items from inbox
    """
    archived_ids = set()

    for exp in expansions:
        archive_expansion(exp, archive_dir)
        archived_ids.add(exp.item_id)

        # Remove from expanded/
        exp_path = expanded_dir / f"{exp.item_id}.json"
        if exp_path.exists():
            exp_path.unlink()

    # Rewrite inbox without archived items
    if inbox_path.exists():
        lines = []
        with inbox_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    if data.get("id") not in archived_ids:
                        lines.append(line)

        with inbox_path.open("w") as f:
            for line in lines:
                f.write(line + "\n")


def get_context_summary(expansions: list[Expansion], max_items: int = 5) -> str:
    """
    Create a summary of prior expansions to provide as context.
    Used to give the agent memory of related past research.
    """
    if not expansions:
        return ""

    # Sort by date, most recent first
    sorted_exps = sorted(expansions, key=lambda e: e.expanded_at, reverse=True)[:max_items]

    lines = ["## Related prior research\n"]
    for exp in sorted_exps:
        lines.append(f"### {exp.source_url or exp.item_id}")
        lines.append(f"**Topics:** {', '.join(exp.topics)}")
        lines.append(f"**Summary:** {exp.source_summary[:300]}...")
        lines.append(f"**Key points:** {'; '.join(exp.key_points[:3])}")
        lines.append("")

    return "\n".join(lines)
