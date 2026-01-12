# Daily Digest

Personal intelligence agent that expands curated sources into synthesized insights.

Status: Minimal first pass for eval-driven iteration. Core flow functional.

## Flow

```
inbox.jsonl → expand (agent) → digest → archive by topic
```

### Agent Graph

```mermaid
graph TD
    __start__ --> agent
    agent -.-> tools
    tools --> agent
    agent -. end .-> __end__
```

The agent loops between calling Claude (with tools bound) and executing tool calls until it produces structured JSON output or hits the 10-turn limit.

## Usage

```bash
# Add source to inbox
uv run daily-digest add "https://example.com/article" --note "why interesting"

# Expand all inbox items
uv run daily-digest run

# Generate digest from expansions
uv run daily-digest digest

# View topics in archive
uv run daily-digest topics

# Collect seed URLs for eval dataset
uv run daily-digest seeds collect --categories="agent-evaluation" --target=5 --score --review --output=seeds.jsonl

# List available topic categories
uv run daily-digest seeds categories

# Validate a URL
uv run daily-digest seeds validate --url="https://example.com/article"
```

### Seed Collection

The `seeds` command builds eval datasets by collecting high-quality URLs across topic categories.

```mermaid
graph TD
    __start__ --> collector[Seed Collector Agent]
    collector -.-> tavily[Tavily Search]
    tavily --> collector
    collector -. URLs .-> validate[URL Validation]
    validate --> score{Score?}
    score -- yes --> llm_judge[LLM-as-Judge]
    llm_judge --> review{Review?}
    score -- no --> review
    review -- yes --> human[Interactive Review]
    human --> export[Export JSONL]
    review -- no --> export
    export --> __end__
```

The collector agent uses DeepAgents with Claude Sonnet 4 and Tavily search to find URLs matching topic categories. After collection:
1. **Validation** - Dedup, domain filtering, accessibility checks
2. **Scoring** (optional) - LLM-as-judge rates eval quality 1-5
3. **Review** (optional) - Interactive approve/reject

```bash
# Full workflow: collect → score → review → export
daily-digest seeds collect \
  --categories="agent-evaluation,procedural-memory" \
  --target=5 \
  --score \
  --review \
  --output=approved_seeds.jsonl
```

Options:
- `--categories`: Comma-separated topic categories (default: all)
- `--target`: Seeds per category (default: 8)
- `--score`: AI quality scoring (1-5)
- `--review`: Interactive approve/reject after collection
- `--output`: Export path for JSONL

Review a previously collected file:
```bash
daily-digest seeds review --file=raw.jsonl --output=approved.jsonl
```

### Evaluation

The `eval` command runs evaluators against agent traces to measure expansion quality.

```bash
# Evaluate recent LangSmith traces (code-based evaluators)
daily-digest eval --recent --limit 10

# Include trajectory analysis (agent behavior)
daily-digest eval --recent --trajectory

# Include model-based evaluators (LLM-as-judge)
daily-digest eval --recent --model-based

# Run pass@k variance test
daily-digest eval --pass-at-k 3 --threshold 0.7
```

**Evaluators:**

| Category | Evaluator | What it measures |
|----------|-----------|------------------|
| Code-based | `structure` | Required output fields present |
| Code-based | `efficiency` | No redundant tool calls |
| Code-based | `sources_retrieved` | Agent fetched sources |
| Model-based | `groundedness` | Claims traceable to sources |
| Model-based | `coverage` | Captures essential insights |
| Model-based | `authority` | Sources are authoritative |
| Model-based | `topic_quality` | Semantic groupings vs keywords |
| Trajectory | `trajectory_tool_efficiency` | Optimal tool usage |
| Trajectory | `trajectory_reasoning` | Search strategy quality |
| Trajectory | `trajectory_goal_completion` | Agent achieved goal |

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

# LangSmith tracing (optional)
export LANGSMITH_API_KEY=...
export LANGSMITH_TRACING=true  # disabled by default
export LANGSMITH_PROJECT=daily-digest
```
