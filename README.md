# Daily Digest

Personal intelligence agent that expands curated sources into synthesized insights.

Status: Minimal first pass for eval-driven iteration. Core flow functional.

## Flow

```
inbox.jsonl → expand (agent) → digest → archive by topic
```

## Usage

```bash
# Add source to inbox
uv run python -m src.daily_digest.cli add "https://example.com/article" --note "why interesting"

# Expand all inbox items
uv run python -m src.daily_digest.cli run

# Generate digest from expansions
uv run python -m src.daily_digest.cli digest

# View topics in archive
uv run python -m src.daily_digest.cli topics
```

## Structure

```
digests/
  SOURCES.md      # Curated sources tracker (human-readable)
  2026-01-11.md   # Daily digest output
archive/          # Expansions filed by topic
trajectories/     # Agent run logs for analysis
WORLD_VIEW.md     # Cross-session synthesis
```

## Stack

- LangGraph agent with Claude Sonnet 4
- Tavily web search
- GitHub API for repo info
- SSRF protection on URL fetching

## Config

```bash
export ANTHROPIC_API_KEY=...
export TAVILY_API_KEY=...
export GITHUB_TOKEN=...  # optional
```
