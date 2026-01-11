"""CLI for daily-digest agent."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .agent import expand_item
from .trajectory import TrajectoryLogger
from .archive import (
    archive_and_cleanup,
    find_related_expansions,
    get_context_summary,
    list_topics,
)
from .digest import create_digest, generate_digest_markdown
from .models import Expansion, InboxItem, ItemType

console = Console()

DEFAULT_INBOX = Path("inbox.jsonl")
DEFAULT_EXPANDED = Path("expanded")
DEFAULT_DIGESTS = Path("digests")
DEFAULT_ARCHIVE = Path("archive")
DEFAULT_FETCH_CACHE = Path("fetch_cache")
DEFAULT_WORLD_VIEW = Path("WORLD_VIEW.md")


def load_inbox(path: Path) -> list[InboxItem]:
    """Load inbox items from JSONL file."""
    if not path.exists():
        return []
    items = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                items.append(InboxItem(**data))
    return items


def save_inbox_item(item: InboxItem, path: Path) -> None:
    """Append item to inbox."""
    with path.open("a") as f:
        f.write(item.model_dump_json() + "\n")


def save_expansion(expansion: Expansion, output_dir: Path) -> Path:
    """Save expansion to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{expansion.item_id}.json"
    with path.open("w") as f:
        f.write(expansion.model_dump_json(indent=2))
    return path


def load_expansions(output_dir: Path) -> list[Expansion]:
    """Load all expansions from directory."""
    if not output_dir.exists():
        return []
    expansions = []
    for path in output_dir.glob("*.json"):
        with path.open() as f:
            data = json.load(f)
            expansions.append(Expansion(**data))
    return expansions


def get_processed_ids(output_dir: Path) -> set[str]:
    """Get IDs of already processed items."""
    if not output_dir.exists():
        return set()
    return {p.stem for p in output_dir.glob("*.json")}


def store_local_content(item_id: str, content_source: str) -> Path:
    """Store content locally and return the path."""
    DEFAULT_FETCH_CACHE.mkdir(parents=True, exist_ok=True)

    # Read content from file or stdin
    if content_source == "-":
        console.print("[dim]Paste content (Ctrl+D when done):[/dim]")
        text = sys.stdin.read()
    else:
        source_path = Path(content_source)
        if not source_path.exists():
            raise FileNotFoundError(f"Content file not found: {content_source}")
        text = source_path.read_text()

    # Store with item id
    content_path = DEFAULT_FETCH_CACHE / f"{item_id}.txt"
    content_path.write_text(text)
    return content_path


def load_local_content(path: str | Path) -> str | None:
    """Load locally stored content."""
    p = Path(path)
    if p.exists():
        return p.read_text()
    return None


async def cmd_add(args: argparse.Namespace) -> None:
    """Add item to inbox."""
    content = args.content
    note = args.note
    local_content_path = None

    # Generate ID first so we can use it for content storage
    item_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Handle local content for gated sources
    if args.file:
        try:
            stored_path = store_local_content(item_id, args.file)
            local_content_path = str(stored_path)
            console.print(f"[green]Stored content at {stored_path}[/green]")
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            return

    # Detect type and create item
    if content.startswith(("http://", "https://")):
        item = InboxItem(
            id=item_id,
            content=content,
            item_type=ItemType.URL,
            note=note,
            local_content=local_content_path,
        )
    else:
        item = InboxItem(
            id=item_id,
            content=content,
            item_type=ItemType.IDEA,
            note=note,
        )

    save_inbox_item(item, DEFAULT_INBOX)
    console.print(f"[green]Added to inbox:[/green] {content}")
    if note:
        console.print(f"[dim]Note: {note}[/dim]")
    if local_content_path:
        console.print(f"[dim]Local content: {local_content_path}[/dim]")


async def cmd_run(args: argparse.Namespace) -> None:
    """Process inbox items."""
    items = load_inbox(DEFAULT_INBOX)
    if not items:
        console.print("[yellow]Inbox is empty. Add items with 'daily-digest add <url-or-idea>'[/yellow]")
        return

    processed = get_processed_ids(DEFAULT_EXPANDED)
    pending = [item for item in items if item.id not in processed]

    if not pending:
        console.print("[green]All items already processed.[/green]")
        return

    # Initialize trajectory logger
    trajectory = TrajectoryLogger()
    console.print(f"[dim]Trajectory run ID: {trajectory.run_id}[/dim]")

    # Load known topics from archive for consistency
    known_topics = list_topics(DEFAULT_ARCHIVE)
    if known_topics:
        console.print(f"[dim]Known topics: {', '.join(known_topics)}[/dim]")

    # Load world view for research anchoring
    world_view_context = None
    if DEFAULT_WORLD_VIEW.exists():
        world_view_context = DEFAULT_WORLD_VIEW.read_text()
        console.print(f"[dim]Loaded world view ({len(world_view_context)} chars)[/dim]")

    console.print(f"\n[bold]Processing {len(pending)} item(s)...[/bold]\n")

    for item in pending:
        console.print(Panel(f"[bold]{item.content}[/bold]\n{item.note or ''}", title=f"Expanding {item.id}"))

        # Find related prior expansions from archive
        prior_context = None
        if known_topics:
            # Use all topics as potential matches for now
            # Future: smarter topic matching based on item content
            related = find_related_expansions(DEFAULT_ARCHIVE, known_topics, exclude_ids={item.id})
            if related:
                prior_context = get_context_summary(related)
                console.print(f"[dim]Including {len(related)} prior expansion(s) as context[/dim]")

        # Load local content if available
        local_content = None
        if item.local_content:
            local_content = load_local_content(item.local_content)
            if local_content:
                console.print(f"[dim]Using locally stored content ({len(local_content)} chars)[/dim]")

        try:
            expansion = await expand_item(
                item,
                prior_context=prior_context,
                known_topics=known_topics,
                local_content=local_content,
                trajectory_logger=trajectory,
                world_view=world_view_context,
            )
            path = save_expansion(expansion, DEFAULT_EXPANDED)
            console.print(f"[green]Saved expansion to {path}[/green]")

            # Show summary
            console.print(f"\n[bold]Summary:[/bold] {expansion.source_summary[:200]}...")
            if expansion.key_points:
                console.print(f"[bold]Key points:[/bold] {len(expansion.key_points)}")
            if expansion.related:
                console.print(f"[bold]Related items found:[/bold] {len(expansion.related)}")
            if expansion.topics:
                console.print(f"[bold]Topics:[/bold] {', '.join(expansion.topics)}")
            console.print()

        except Exception as e:
            trajectory.log_error(item.id, str(e))
            console.print(f"[red]Error processing {item.id}: {e}[/red]")

    # Save trajectory
    trajectory_path = trajectory.save()
    console.print(f"\n[dim]Trajectory saved to {trajectory_path}[/dim]")


async def cmd_digest(args: argparse.Namespace) -> None:
    """Generate daily digest and archive expansions."""
    items = load_inbox(DEFAULT_INBOX)
    items_by_id = {item.id: item for item in items}

    expansions = load_expansions(DEFAULT_EXPANDED)
    if not expansions:
        console.print("[yellow]No expansions yet. Run 'daily-digest run' first.[/yellow]")
        return

    # Filter to today's expansions if requested
    today = datetime.now().strftime("%Y%m%d")
    if not args.all:
        expansions = [e for e in expansions if e.item_id.startswith(today)]
        if not expansions:
            console.print(f"[yellow]No expansions from today ({today}). Use --all to include all.[/yellow]")
            return

    console.print(f"[bold]Generating digest from {len(expansions)} expansion(s)...[/bold]\n")

    digest = await create_digest(expansions, items_by_id)
    markdown = generate_digest_markdown(digest, items_by_id)

    # Save digest
    DEFAULT_DIGESTS.mkdir(parents=True, exist_ok=True)
    digest_path = DEFAULT_DIGESTS / f"{digest.date}.md"
    with digest_path.open("w") as f:
        f.write(markdown)

    console.print(f"[green]Saved digest to {digest_path}[/green]\n")
    console.print(Panel(markdown, title="Daily Digest"))

    # Archive expansions and clean up
    if not args.no_archive:
        archive_and_cleanup(expansions, DEFAULT_EXPANDED, DEFAULT_ARCHIVE, DEFAULT_INBOX)
        topics_used = set()
        for exp in expansions:
            topics_used.update(exp.topics)
        console.print(f"\n[green]Archived {len(expansions)} expansion(s) under topics: {', '.join(topics_used) or 'uncategorized'}[/green]")
        console.print("[dim]Inbox cleared. Expansions moved to archive.[/dim]")


async def cmd_show(args: argparse.Namespace) -> None:
    """Show inbox contents."""
    items = load_inbox(DEFAULT_INBOX)
    processed = get_processed_ids(DEFAULT_EXPANDED)

    if not items:
        console.print("[yellow]Inbox is empty.[/yellow]")
        return

    console.print(f"[bold]Inbox ({len(items)} items):[/bold]\n")
    for item in items:
        status = "[green]expanded[/green]" if item.id in processed else "[yellow]pending[/yellow]"
        console.print(f"  {item.id} [{status}] {item.content}")
        if item.note:
            console.print(f"    [dim]{item.note}[/dim]")


async def cmd_topics(args: argparse.Namespace) -> None:
    """Show archive topics."""
    from .archive import load_topic_expansions

    topics = list_topics(DEFAULT_ARCHIVE)
    if not topics:
        console.print("[yellow]Archive is empty. Run digest to archive expansions.[/yellow]")
        return

    console.print(f"[bold]Archive ({len(topics)} topics):[/bold]\n")
    for topic in sorted(topics):
        expansions = load_topic_expansions(DEFAULT_ARCHIVE, topic)
        console.print(f"  [cyan]{topic}[/cyan] ({len(expansions)} items)")
        for exp in expansions[:3]:  # Show first 3
            console.print(f"    - {exp.source_url or exp.item_id}")
        if len(expansions) > 3:
            console.print(f"    [dim]... and {len(expansions) - 3} more[/dim]")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Personal Intelligence Agent - expand seeds into research digests"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    add_parser = subparsers.add_parser("add", help="Add item to inbox")
    add_parser.add_argument("content", help="URL or idea/question to add")
    add_parser.add_argument("-n", "--note", help="Why you found this interesting")
    add_parser.add_argument("-f", "--file", help="File with content for gated sources (use '-' for stdin)")

    # run command
    run_parser = subparsers.add_parser("run", help="Process pending inbox items")

    # digest command
    digest_parser = subparsers.add_parser("digest", help="Generate daily digest")
    digest_parser.add_argument("--all", action="store_true", help="Include all expansions, not just today's")
    digest_parser.add_argument("--no-archive", action="store_true", help="Don't archive expansions after digest")

    # show command
    show_parser = subparsers.add_parser("show", help="Show inbox contents")

    # topics command
    topics_parser = subparsers.add_parser("topics", help="Show archive topics")

    args = parser.parse_args()

    # Run async command
    if args.command == "add":
        asyncio.run(cmd_add(args))
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "digest":
        asyncio.run(cmd_digest(args))
    elif args.command == "show":
        asyncio.run(cmd_show(args))
    elif args.command == "topics":
        asyncio.run(cmd_topics(args))


if __name__ == "__main__":
    main()
