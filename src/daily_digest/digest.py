"""Generate daily digest from expansions."""

from datetime import datetime

import anthropic
from langsmith import traceable

from .models import Digest, DigestEntry, Expansion, InboxItem


def generate_digest_markdown(digest: Digest, items: dict[str, InboxItem]) -> str:
    """Render digest as markdown."""
    lines = [
        f"# Daily Digest - {digest.date}",
        "",
    ]

    if not digest.entries:
        lines.append("*No items processed today.*")
        return "\n".join(lines)

    # Entries
    lines.append("## What Was Processed")
    lines.append("")
    for entry in digest.entries:
        item = items.get(entry.item_id)
        source = item.content if item else "Unknown source"
        lines.append(f"### {entry.title}")
        lines.append(f"*Source: {source}*")
        lines.append("")
        lines.append(entry.one_liner)
        lines.append("")
        lines.append(f"**Key finding:** {entry.key_finding}")
        if entry.worth_following:
            lines.append("")
            lines.append("**Worth following:**")
            for link in entry.worth_following:
                lines.append(f"- {link}")
        lines.append("")

    # Cross-connections
    if digest.cross_connections:
        lines.append("## Connections")
        lines.append("")
        for conn in digest.cross_connections:
            lines.append(f"- {conn}")
        lines.append("")

    # Open threads
    if digest.open_threads:
        lines.append("## Open Threads")
        lines.append("")
        for thread in digest.open_threads:
            lines.append(f"- {thread}")
        lines.append("")

    return "\n".join(lines)


@traceable(name="create_digest", run_type="chain", tags=["digest"])
async def create_digest(
    expansions: list[Expansion], items: dict[str, InboxItem]
) -> Digest:
    """Create a digest from expansions using Claude for synthesis."""
    if not expansions:
        return Digest(date=datetime.now().strftime("%Y-%m-%d"), entries=[])

    # Prepare expansion summaries for Claude
    expansion_texts = []
    for exp in expansions:
        item = items.get(exp.item_id)
        source = item.content if item else "Unknown"
        note = item.note if item else None

        text = f"""
Item ID: {exp.item_id}
Source: {source}
User's focus: {note or 'None specified'}

Summary: {exp.source_summary}

Key points:
{chr(10).join('- ' + p for p in exp.key_points)}

Assessment: {exp.assessment}

Related items found:
{chr(10).join(f'- {r.title}: {r.url} ({r.relevance})' for r in exp.related) or 'None'}
"""
        expansion_texts.append(text)

    client = anthropic.AsyncAnthropic()

    prompt = f"""Synthesize these research expansions into a scannable daily digest.

EXPANSIONS:
{'---'.join(expansion_texts)}

For each expansion, provide:
1. A short title (3-5 words)
2. A one-liner summary
3. The single most important finding
4. 0-3 links worth following up (from the related items)

Also identify:
- Cross-connections between items (if any)
- Open threads worth investigating further

Output JSON:
```json
{{
  "entries": [
    {{
      "item_id": "...",
      "title": "...",
      "one_liner": "...",
      "key_finding": "...",
      "worth_following": ["url1", "url2"]
    }}
  ],
  "cross_connections": ["Connection 1", "Connection 2"],
  "open_threads": ["Thread 1", "Thread 2"]
}}
```"""

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse response
    text = response.content[0].text
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0]
        import json

        data = json.loads(json_str)

        entries = [DigestEntry(**e) for e in data.get("entries", [])]
        return Digest(
            date=datetime.now().strftime("%Y-%m-%d"),
            entries=entries,
            cross_connections=data.get("cross_connections", []),
            open_threads=data.get("open_threads", []),
        )

    # Fallback
    return Digest(
        date=datetime.now().strftime("%Y-%m-%d"),
        entries=[
            DigestEntry(
                item_id=exp.item_id,
                title="Expansion",
                one_liner=exp.source_summary[:100],
                key_finding=exp.key_points[0] if exp.key_points else "See full expansion",
            )
            for exp in expansions
        ],
    )
