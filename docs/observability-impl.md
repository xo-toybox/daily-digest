# Observability Implementation Guide

> Implementation details for [observability.md](./observability.md). Code snippets, configs, and step-by-step checklist.

## Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing
    "langsmith>=0.2.0",
    "openevals>=0.1.0",
    "deepagents>=0.1.0",  # For seed input collection pipeline
]
```

## Environment Variables

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=...
export LANGCHAIN_PROJECT=daily-digest  # or daily-digest-dev
```

---

## Step 1: Tracing Foundation

### Code Changes

**agent.py** — LangGraph traces automatically. Remove manual trajectory logging:

```python
# Before: manual logging
if trajectory_logger:
    trajectory_logger.log_tool_call(...)

# After: automatic (LangGraph handles it)
# Optional: add metadata for filtering
from langsmith import traceable

@traceable(metadata={"component": "expand"}, tags=["agent"])
async def expand_item(item: InboxItem, ...) -> Expansion:
    ...
```

**digest.py** — Wrap direct Anthropic calls:

```python
from langsmith import traceable

@traceable(name="create_digest", run_type="chain", tags=["digest"])
async def create_digest(expansions: list[Expansion], items: dict[str, InboxItem]) -> Digest:
    ...
```

**tools.py** — Trace tool implementations:

```python
from langsmith import traceable

@traceable(run_type="tool", tags=["fetch"])
async def fetch_url(url: str) -> FetchResult:
    ...
```

### Local Export (Dev Mode)

```python
# cli.py
import os
from langsmith import Client

def export_traces_local(project_name: str, run_id: str):
    """Export LangSmith traces to local JSON for offline analysis."""
    if os.environ.get("DAILY_DIGEST_LOCAL_EXPORT"):
        client = Client()
        runs = list(client.list_runs(project_name=project_name, run_ids=[run_id]))
        # Save to trajectories/ for backwards compatibility
        ...
```

Alternative: use `langsmith export` CLI command.

---

## Step 2: Evaluators

### Expansion Evaluators

```python
# src/daily_digest/eval/expansion_evaluators.py
from langsmith.evaluation import evaluate
from openevals.llm import create_llm_as_judge

# ============================================================
# CODE-BASED EVALUATORS (fast, objective, run first)
# ============================================================

def structure_evaluator(inputs: dict, outputs: dict) -> dict:
    """Check if output has required structure."""
    required = ["source_summary", "key_points", "related", "topics"]
    missing = [k for k in required if k not in outputs or not outputs[k]]
    return {
        "score": 1.0 if not missing else 0.0,
        "pass": len(missing) == 0,
        "missing_fields": missing
    }

def efficiency_evaluator(run, example) -> dict:
    """Evaluate agent tool usage efficiency."""
    tool_calls = [c for c in run.child_runs if c.run_type == "tool"]
    turns_used = run.outputs.get("turn_count", 0)

    # Check for redundant patterns
    redundant = 0
    urls_fetched = set()
    for tc in tool_calls:
        if tc.name in ["fetch_url", "github_repo"]:
            url = tc.inputs.get("url") or f"github.com/{tc.inputs.get('owner')}/{tc.inputs.get('repo')}"
            if url in urls_fetched:
                redundant += 1
            urls_fetched.add(url)

    return {
        "score": 1 - (redundant / max(len(tool_calls), 1)),
        "tool_calls": len(tool_calls),
        "turns_used": turns_used,
        "redundant": redundant,
        "efficient": redundant == 0 and turns_used <= 8
    }

def sources_retrieved_evaluator(run, example) -> dict:
    """Binary check: did agent retrieve any sources?"""
    tool_calls = [c for c in run.child_runs if c.run_type == "tool"]
    fetch_tools = ["fetch_url", "fetch_tweet", "web_search", "github_repo"]
    retrieved = any(tc.name in fetch_tools for tc in tool_calls)
    return {"score": 1.0 if retrieved else 0.0, "pass": retrieved}

# ============================================================
# MODEL-BASED EVALUATORS (nuanced, run after code checks pass)
# ============================================================

groundedness_evaluator = create_llm_as_judge(
    prompt="""Evaluate if the expansion's claims are grounded in retrieved sources.

    Source Summary: {outputs[source_summary]}
    Key Points: {outputs[key_points]}
    Research Notes: {outputs[research_notes]}

    Score 1-5:
    5: All claims traceable to sources, no hallucination
    4: Most claims grounded, minor unsupported details
    3: Mix of grounded and speculative claims
    2: Significant claims lack source support
    1: Appears to hallucinate or fabricate information

    Explain which specific claims lack grounding.
    """,
    model="claude-sonnet-4-20250514"
)

coverage_evaluator = create_llm_as_judge(
    prompt="""Evaluate if the expansion captures the essential insights from the source.

    Original URL/Content: {inputs[content]}
    User's Interest: {inputs[note]}
    Summary Produced: {outputs[source_summary]}
    Key Points: {outputs[key_points]}

    Score 1-5:
    5: Comprehensive - captures all important insights, nothing significant missed
    4: Good coverage - main points covered, minor gaps
    3: Partial - captures obvious points but misses nuance
    2: Shallow - only surface-level extraction
    1: Inadequate - misses core content

    What important aspects were missed?
    """,
    model="claude-sonnet-4-20250514"
)

authority_evaluator = create_llm_as_judge(
    prompt="""Evaluate if related items come from authoritative sources.

    Related Items Found:
    {outputs[related]}

    Score 1-5:
    5: All sources are authoritative (official docs, primary authors, established publications)
    4: Mostly authoritative with minor exceptions
    3: Mix of authoritative and questionable sources
    2: Relies heavily on low-authority sources
    1: Sources are unreliable or inappropriate

    Which sources lack authority and why?
    """,
    model="claude-sonnet-4-20250514"
)

topic_evaluator = create_llm_as_judge(
    prompt="""Evaluate if topics are semantic groupings (problem spaces) vs keywords.

    Good: "building-reliable-ai-systems" (problem space)
    Bad: "evals", "testing", "monitoring" (keywords)

    Topics: {outputs[topics]}
    Content Summary: {outputs[source_summary]}

    Score 1-5:
    5: All topics are meaningful semantic groupings
    3: Mix of semantic and keyword-style
    1: All topics are superficial keywords
    """,
    model="claude-sonnet-4-20250514"
)
```

### Digest Evaluators

```python
# src/daily_digest/eval/digest_evaluators.py
from openevals.llm import create_llm_as_judge

connection_evaluator = create_llm_as_judge(
    prompt="""Evaluate if cross-connections are insightful vs obvious.

    Expansions processed: {inputs[expansion_summaries]}
    Cross-connections identified: {outputs[cross_connections]}

    Score 1-5:
    5: Connections reveal non-obvious relationships
    3: Connections are logical but surface-level
    1: Connections are trivial or missing
    """,
    model="claude-sonnet-4-20250514"
)

actionability_evaluator = create_llm_as_judge(
    prompt="""Evaluate if open threads are actionable research questions.

    Open threads: {outputs[open_threads]}

    Score 1-5:
    5: Clear next steps, specific questions to investigate
    3: General directions but vague
    1: Too abstract to act on
    """,
    model="claude-sonnet-4-20250514"
)

synthesis_evaluator = create_llm_as_judge(
    prompt="""Evaluate overall synthesis quality.

    Input expansions: {inputs[expansion_count]} items
    Digest entries: {outputs[entries]}
    Cross-connections: {outputs[cross_connections]}
    Open threads: {outputs[open_threads]}

    Is the digest:
    - More than sum of parts? (synthesis vs summarization)
    - Specific not generic?
    - Worth the compute spent?

    Score 1-5 with explanation.
    """,
    model="claude-sonnet-4-20250514"
)
```

### Non-Determinism Testing

```python
# src/daily_digest/eval/pass_at_k.py

async def eval_pass_at_k(item: InboxItem, k: int = 3, threshold: float = 0.7) -> dict:
    """Run expansion k times, check if any passes threshold."""
    scores = []
    for _ in range(k):
        expansion = await expand_item(item)
        score = await evaluate_expansion(expansion)
        scores.append(score)
    return {
        "pass@k": max(scores) >= threshold,
        "pass^k": min(scores) >= threshold,
        "variance": max(scores) - min(scores),
        "scores": scores
    }
```

### Running Evaluations

```python
from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

# Create dataset from production traces
client.create_dataset("expansion-golden", description="High-quality expansion examples")

# Run evaluation
results = evaluate(
    expand_item,  # target function
    data="expansion-golden",
    evaluators=[structure_evaluator, groundedness_evaluator, coverage_evaluator, topic_evaluator],
    experiment_prefix="expansion-v1"
)
```

---

## Step 3: Dataset Management

### Building Datasets from Production

```python
# 1. Identify failures and poor quality runs
failed_runs = client.list_runs(
    project_name="daily-digest",
    filter='or(eq(status, "error"), lt(feedback_scores["quality"], 3))'
)

# 2. Identify high-quality runs for positive examples
good_runs = client.list_runs(
    project_name="daily-digest",
    filter='gt(feedback_scores["quality"], 4)'
)

# 3. Add to dataset with quality tier metadata
for run in failed_runs:
    client.create_example(
        dataset_name="expansion-golden",
        inputs=run.inputs,
        outputs=run.outputs,  # Keep original bad output for regression testing
        metadata={"quality_tier": "needs_improvement", "failure_type": "..."}
    )

# 4. Manually curate expected outputs for failure cases
# This is where human effort goes - defining what SHOULD have been produced
```

---

## Step 4: Seed Input Collection Pipeline

### DeepAgents Configuration

```python
# src/daily_digest/eval/seed_collector.py
from deepagents import create_deep_agent
from langsmith import Client

exploration_agent = create_deep_agent(
    model="claude-sonnet-4-20250514",
    tools=[web_search],  # web_search ONLY - no fabricated APIs
    interrupt_on={
        "web_search": {
            "allowed_decisions": ["approve", "reject"],
            # Only interrupt if results exceed threshold (batch approval)
            "condition": lambda results: len(results) > 10
        }
    },
    system_prompt="""You are a seed input collector for an eval dataset.

    CONSTRAINTS:
    - Search within the provided topic category ONLY
    - Find 5-10 high-quality URLs per category
    - Prioritize: authoritative sources, substantive content, diverse perspectives
    - STOP when you have enough candidates (don't over-search)

    TOPIC CATEGORY: {topic_category}
    SEARCH CONSTRAINTS: {constraints}
    """
)

# Subagent per topic category (spawned by main agent)
# Topic categories defined in separate design session
```

### Validation Functions

```python
import httpx
from urllib.parse import urlparse

async def validate_candidate(url: str, existing_urls: set[str]) -> dict:
    """Code-based validation (fast, run on all candidates)."""

    # 1. URL normalization & dedup
    normalized = normalize_url(url)
    if normalized in existing_urls:
        return {"valid": False, "reason": "duplicate"}

    # 2. Accessibility check
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.head(url, follow_redirects=True, timeout=10)
            if resp.status_code >= 400:
                return {"valid": False, "reason": f"status_{resp.status_code}"}
        except httpx.RequestError as e:
            return {"valid": False, "reason": f"unreachable: {e}"}

    # 3. Domain allowlist (optional, for quality control)
    domain = urlparse(url).netloc
    if is_known_low_quality(domain):
        return {"valid": False, "reason": "low_quality_domain"}

    return {"valid": True, "normalized_url": normalized}

def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    parsed = urlparse(url)
    # Remove tracking params, normalize path
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()
```

### AI Quality Scorer

```python
from openevals.llm import create_llm_as_judge

seed_quality_scorer = create_llm_as_judge(
    prompt="""Evaluate if this URL is good eval material for a research expansion agent.

    URL: {url}
    Title/Description: {metadata}
    Topic Category: {category}

    Consider:
    - Is the content substantive (not just a landing page)?
    - Is this representative of the category?
    - Would expanding this test the agent's capabilities well?
    - Is the source authoritative?

    Score 1-5:
    5: Excellent eval material - substantive, representative, tests edge cases
    4: Good material - solid content, clear category fit
    3: Acceptable - usable but not ideal
    2: Marginal - thin content or poor category fit
    1: Reject - not suitable for eval

    Return score and brief reasoning.
    """,
    model="claude-sonnet-4-20250514"
)
```

### LangSmith Annotation Queue Setup

```python
from langsmith import Client

client = Client()

# Create annotation queue for human review
client.create_annotation_queue(
    name="seed-input-review",
    description="Review AI-scored seed inputs for eval dataset",
    rubric_items=[
        {"name": "quality", "description": "Is this good eval material?", "scale": 5},
        {"name": "category_fit", "description": "Does it fit the assigned category?", "scale": 5},
    ]
)

# Automation: route high-scoring candidates to queue
# (Configure in LangSmith UI: Automations → Add Rule)
# Filter: feedback_scores["ai_quality"] >= 3
# Action: Add to Annotation Queue "seed-input-review"
```

### Export to Eval Input Format

```python
from langsmith import Client
from pathlib import Path
import json

def export_to_eval_inputs(dataset_name: str = "seed-inputs-gold"):
    """Transform approved items to inbox.json format."""
    client = Client()

    # Pull approved items from LangSmith
    examples = list(client.list_examples(dataset_name=dataset_name))

    # Group by category
    by_category: dict[str, list] = {}
    for ex in examples:
        category = ex.metadata.get("category", "uncategorized")
        inbox_item = {
            "item_type": ex.inputs.get("item_type", "url"),
            "content": ex.inputs["url"],
            "note": ex.inputs.get("note", ""),
        }
        by_category.setdefault(category, []).append(inbox_item)

    # Write to local JSON (version controlled)
    output_dir = Path("datasets/eval_inputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    for category, items in by_category.items():
        output_path = output_dir / f"{category}.json"
        with open(output_path, "w") as f:
            json.dump({"items": items, "category": category}, f, indent=2)
        print(f"Wrote {len(items)} items to {output_path}")

    # Also write combined file
    all_items = [item for items in by_category.values() for item in items]
    with open(output_dir / "all.json", "w") as f:
        json.dump({"items": all_items, "count": len(all_items)}, f, indent=2)

# Run after human review session
export_to_eval_inputs()
```

### Topic Categories (Placeholder)

```python
TOPIC_CATEGORIES = {
    # To be defined in dedicated session - critical for bounded exploration
    # Each category should have:
    # - name: str
    # - description: str
    # - search_constraints: list[str]  # keywords, domains to include/exclude
    # - target_count: int  # how many seeds per category
}
```

---

## Implementation Checklist

### Step 1: Tracing Foundation
- [ ] Add `langsmith` to dependencies
- [ ] Set up environment variables
- [ ] Add @traceable to `digest.py` (direct Anthropic calls)
- [ ] Add @traceable to tool implementations
- [ ] Remove TrajectoryLogger usage (keep file for reference)
- [ ] Add optional local export mode

### Step 2: Evaluation Infrastructure
- [ ] Create `src/daily_digest/eval/` directory
- [ ] Implement expansion_evaluators.py
- [ ] Implement digest_evaluators.py
- [ ] Create initial golden dataset (5-10 examples manually)
- [ ] Add `daily-digest eval` CLI command

### Step 3: Production Feedback Loop
- [ ] Set up annotation queue for manual review
- [ ] Build dataset from production traces
- [ ] Configure alerts in LangSmith UI
- [ ] Create monitoring dashboard

### Step 4: Seed Input Collection Pipeline
- [ ] **Design topic categories** (dedicated session - critical for bounded exploration)
- [ ] Add `deepagents` to dependencies
- [ ] Implement exploration agent with web_search tool
- [ ] Implement validation functions (accessibility, dedup, schema)
- [ ] Implement AI quality scorer
- [ ] Set up LangSmith annotation queue "seed-input-review"
- [ ] Configure automation rules (score >= 3 → queue)
- [ ] Implement export_to_eval_inputs() function
- [ ] Bootstrap initial 20-50 seed inputs across categories
