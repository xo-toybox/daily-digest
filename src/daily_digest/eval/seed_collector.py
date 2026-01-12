"""Seed input collection for eval dataset.

Collects, validates, and scores URLs for evaluation dataset building.
Uses topic categories from docs/topic-taxonomy.md.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlparse, parse_qs, urlencode

import httpx
from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langsmith import traceable
from pydantic import BaseModel, Field

DEFAULT_LANGSMITH_PROJECT = "daily-digest-datagen"


def _ensure_tracing_config():
    """Set default project name if not configured. Tracing defaults to off."""
    if not os.environ.get("LANGSMITH_PROJECT"):
        os.environ["LANGSMITH_PROJECT"] = DEFAULT_LANGSMITH_PROJECT


# Topic categories from topic-taxonomy.md
TOPIC_CATEGORIES = {
    # Engineering Layer
    "context-offloading": {
        "layer": "engineering",
        "description": "Filesystem for persistent context",
        "keywords": ["context management", "summarization", "tool result storage"],
    },
    "context-caching": {
        "layer": "engineering",
        "description": "Prompt caching for cost/latency",
        "keywords": ["prompt caching", "cache hit rate", "prefix reuse"],
    },
    "context-isolation": {
        "layer": "engineering",
        "description": "Sub-agents with separate windows",
        "keywords": ["sub-agents", "parallel execution", "map-reduce agents"],
    },
    "progressive-disclosure": {
        "layer": "engineering",
        "description": "Just-in-time information loading",
        "keywords": ["MCP", "tool indexing", "skill frontmatter"],
    },
    "computer-use": {
        "layer": "engineering",
        "description": "Give agents a computer",
        "keywords": ["computer use", "shell access", "OS primitives", "Claude Code"],
    },
    "human-in-the-loop": {
        "layer": "engineering",
        "description": "Verification and approval patterns",
        "keywords": ["human in the loop", "approval workflow", "stop hooks"],
    },
    "metacognition": {
        "layer": "engineering",
        "description": "Self-assessment and calibration",
        "keywords": ["metacognition", "confidence estimation", "self-assessment"],
    },
    "procedural-memory": {
        "layer": "engineering",
        "description": "Skill libraries and reuse",
        "keywords": ["procedural memory", "skill library", "ReMe", "Voyager"],
    },
    "agent-evaluation": {
        "layer": "engineering",
        "description": "Measuring agent quality",
        "keywords": ["agent evaluation", "benchmarks", "pass@k", "evals"],
    },
    "trace-driven-development": {
        "layer": "engineering",
        "description": "Traces as documentation",
        "keywords": ["tracing", "observability", "LangSmith", "reasoning chains"],
    },
    # Product Layer
    "transparency-patterns": {
        "layer": "product",
        "description": "Making agent reasoning visible",
        "keywords": ["agent transparency", "thought logs", "action explanations"],
    },
    "autonomy-calibration": {
        "layer": "product",
        "description": "User control over proactiveness",
        "keywords": ["agent autonomy", "permission settings", "proactiveness"],
    },
    "progressive-autonomy": {
        "layer": "product",
        "description": "Staged deployment",
        "keywords": ["shadow mode", "staged rollout", "agent deployment"],
    },
    "error-recovery-ux": {
        "layer": "product",
        "description": "Graceful degradation",
        "keywords": ["error recovery", "agent rollback", "human escalation"],
    },
    # Research Layer
    "world-models": {
        "layer": "research",
        "description": "Physics-aware reasoning",
        "keywords": ["world models", "spatial reasoning", "physics simulation"],
    },
    "reward-hacking": {
        "layer": "research",
        "description": "Specification gaming",
        "keywords": ["reward hacking", "specification gaming", "Goodhart's Law"],
    },
    "cot-faithfulness": {
        "layer": "research",
        "description": "Do explanations reflect reasoning?",
        "keywords": ["chain of thought", "faithfulness", "interpretability"],
    },
}

# Known low-quality domains to skip
LOW_QUALITY_DOMAINS = {
    "pinterest.com",
    "quora.com",
    "medium.com",  # Often paywalled/low quality
    "linkedin.com",  # Gated
    "facebook.com",
    "instagram.com",
    "youtube.com",  # Video content, not suitable for text expansion
    "youtu.be",
}

# Tracking params to strip for normalization
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "fbclid",
    "gclid",
}


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    - Lowercase scheme and netloc
    - Remove tracking parameters
    - Remove trailing slashes
    """
    parsed = urlparse(url)

    # Filter out tracking params
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = {k: v for k, v in query_params.items() if k not in TRACKING_PARAMS}
    new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""

    # Reconstruct normalized URL
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    if new_query:
        normalized += f"?{new_query}"

    return normalized.rstrip("/")


def is_known_low_quality(domain: str) -> bool:
    """Check if domain is in low-quality list."""
    # Check against known low-quality domains
    for low_quality in LOW_QUALITY_DOMAINS:
        if domain.endswith(low_quality):
            return True
    return False


async def validate_url(url: str, existing_urls: set[str] | None = None) -> dict:
    """Validate a URL candidate.

    Args:
        url: URL to validate
        existing_urls: Set of already collected URLs for dedup

    Returns:
        Dict with valid bool, normalized_url, and reason if invalid
    """
    existing_urls = existing_urls or set()

    # 0. Basic sanity check for malformed URLs
    if not url or not url.startswith('http'):
        return {"valid": False, "reason": "not_http_url"}
    if '**' in url or url.endswith('*'):
        return {"valid": False, "reason": "malformed_markdown_url"}

    # 1. Normalize
    try:
        normalized = normalize_url(url)
    except Exception as e:
        return {"valid": False, "reason": f"parse_error: {e}"}

    # 2. Check for duplicate
    if normalized in existing_urls:
        return {"valid": False, "reason": "duplicate", "normalized_url": normalized}

    # 3. Check domain quality
    parsed = urlparse(normalized)
    if is_known_low_quality(parsed.netloc):
        return {"valid": False, "reason": "low_quality_domain", "domain": parsed.netloc}

    # 4. Accessibility check
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        try:
            resp = await client.head(normalized)
            if resp.status_code >= 400:
                return {
                    "valid": False,
                    "reason": f"status_{resp.status_code}",
                    "normalized_url": normalized,
                }
        except httpx.TimeoutException:
            return {"valid": False, "reason": "timeout", "normalized_url": normalized}
        except httpx.RequestError as e:
            return {"valid": False, "reason": f"unreachable: {type(e).__name__}"}

    return {"valid": True, "normalized_url": normalized}


def _get_quality_scorer():
    """Get LLM-as-judge for seed quality. Lazy load."""
    try:
        from openevals.llm import create_llm_as_judge

        return create_llm_as_judge(
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

Return your chosen score.""",
            model="claude-sonnet-4-20250514",
            choices=[1.0, 2.0, 3.0, 4.0, 5.0],
            use_reasoning=True,
        )
    except ImportError:

        def stub(*args, **kwargs):
            return {"score": None, "error": "openevals not installed"}

        return stub


_quality_scorer = None


def score_seed_quality(url: str, metadata: str, category: str) -> dict:
    """Score seed quality using LLM-as-judge.

    Args:
        url: The URL to score
        metadata: Title/description from search results
        category: Topic category name

    Returns:
        Dict with score (1-5) and reasoning
    """
    global _quality_scorer
    if _quality_scorer is None:
        _quality_scorer = _get_quality_scorer()

    # openevals expects prompt variables as direct kwargs
    result = _quality_scorer(
        inputs={},
        outputs={},
        url=url,
        metadata=metadata,
        category=category,
    )
    return {"key": "seed_quality", **result}


def list_categories(layer: str | None = None) -> list[str]:
    """List available topic categories.

    Args:
        layer: Filter by layer (engineering, product, research)

    Returns:
        List of category names
    """
    if layer:
        return [k for k, v in TOPIC_CATEGORIES.items() if v.get("layer") == layer]
    return list(TOPIC_CATEGORIES.keys())


def get_category_info(category: str) -> dict | None:
    """Get info about a topic category."""
    return TOPIC_CATEGORIES.get(category)


def export_seeds_to_jsonl(
    seeds: list[dict],
    output_path: Path,
) -> int:
    """Export validated seeds to JSONL format.

    Args:
        seeds: List of seed dicts with url, category, metadata, score
        output_path: Output file path

    Returns:
        Number of seeds exported
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        for seed in seeds:
            # Handle both raw seeds (url key) and loaded seeds (content key)
            url = seed.get("url") or seed.get("content", "")

            # Build note from title and relevance if not already present
            note = seed.get("note", "")
            if not note:
                note_parts = []
                if seed.get("title") and seed["title"] not in ("(untitled)", "(extracted from agent output)", ""):
                    note_parts.append(seed["title"])
                if seed.get("relevance"):
                    note_parts.append(seed["relevance"])
                note = " - ".join(note_parts) if note_parts else ""

            # Convert to inbox item format
            item = {
                "item_type": "url",
                "content": url,
                "note": note,
                "category": seed.get("category"),
                "quality_score": seed.get("quality_score"),
            }
            f.write(json.dumps(item) + "\n")

    return len(seeds)


# ============================================================
# Collection Agent with DeepAgents
# ============================================================


class CollectedSeed(BaseModel):
    """A single collected URL with metadata."""
    url: str = Field(description="The URL found")
    title: str = Field(description="Title or description of the content")
    relevance_reason: str = Field(description="Why this URL is relevant to the category")


class CollectionResult(BaseModel):
    """Result of seed collection for a category."""
    category: str = Field(description="Topic category searched")
    seeds: list[CollectedSeed] = Field(description="URLs collected")
    search_count: int = Field(description="Number of searches performed")
    notes: str = Field(description="Any notes about the collection process")


def _create_web_search_tool():
    """Create Tavily search tool for seed collection."""
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_api_key:
        raise ValueError("TAVILY_API_KEY environment variable required for seed collection")

    return TavilySearch(
        max_results=10,
        search_depth="advanced",
        exclude_domains=list(LOW_QUALITY_DOMAINS),
    )


def _get_collection_prompt(category: str, target_count: int = 8) -> str:
    """Build system prompt for collection agent."""
    info = TOPIC_CATEGORIES.get(category, {})
    keywords = info.get("keywords", [])
    description = info.get("description", "")

    return f"""You are a seed input collector for an eval dataset.

OBJECTIVE: Find EXACTLY {target_count} high-quality URLs for the topic category "{category}".

CATEGORY DESCRIPTION: {description}
RELEVANT KEYWORDS: {', '.join(keywords)}

DOMAIN FOCUS: AI/ML agents, LLM systems, machine learning automation.
EXCLUDE: Human psychology, neuroscience, education policy, space/aerospace, unrelated academic fields.

HARD CONSTRAINTS:
- STOP after finding {target_count} good URLs (no more!)
- MAX 2-3 URLs from any single domain/project
- NO search result pages, topic aggregators, or paper listing pages
- NO paywalled content, YouTube videos, or low-quality listicles

QUALITY FILTERS:
- Academic papers: title must contain "agent", "LLM", "language model", or "AI"
- Blogs/guides: must be from AI/ML-focused publications or companies
- GitHub repos: must have clear README about AI agents

SEARCH STRATEGY:
1. Start with 1-2 targeted searches combining category keywords + "AI agent" or "LLM"
2. Stop immediately when you have {target_count} qualifying URLs
3. Do NOT summarize all search results - only report the best {target_count}

OUTPUT FORMAT (use exactly this structure for each URL):
- **URL**: [the full URL]
- **Title**: [article/page title]
- **Why relevant**: [one sentence explaining relevance to {category}]
"""


@traceable(name="collect_seeds", run_type="chain", tags=["seed_collection"])
async def collect_seeds_for_category(
    category: str,
    target_count: int = 8,
    max_searches: int = 5,
) -> CollectionResult:
    """Collect seed URLs for a single topic category using DeepAgents.

    Args:
        category: Topic category name from TOPIC_CATEGORIES
        target_count: Target number of seeds to collect
        max_searches: Maximum number of search queries to run

    Returns:
        CollectionResult with collected seeds and metrics
    """
    from deepagents import create_deep_agent

    if category not in TOPIC_CATEGORIES:
        raise ValueError(f"Unknown category: {category}. Use list_categories() to see available.")

    search_tool = _create_web_search_tool()
    system_prompt = _get_collection_prompt(category, target_count)

    agent = create_deep_agent(
        model="claude-sonnet-4-20250514",
        tools=[search_tool],
        system_prompt=system_prompt,
        name=f"seed_collector_{category}",
    )

    # Invoke the agent
    task_prompt = f"""Find {target_count} high-quality URLs for the "{category}" topic category.

Use the web search tool to find relevant content. After searching, list all the URLs you found with:
1. The URL
2. The title/description
3. Why it's relevant to {category}

Stop after finding enough good candidates or after {max_searches} searches.
"""

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=task_prompt)]},
    )

    # Parse the result - extract URLs and metadata from agent output
    messages = result.get("messages", [])
    seeds = []
    search_count = 0

    import re
    from langchain_core.messages import AIMessage

    # Count tool calls for metrics
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            search_count += len(msg.tool_calls)

    # First pass: look for structured output in AI messages (preferred)
    url_title_pattern = r'-\s*\*\*URL\*\*:\s*(https?://[^\s\n]+)\s*\n-\s*\*\*Title\*\*:\s*([^\n]+)\s*\n-\s*\*\*(?:Why[^*]*)\*\*:\s*([^\n]+)'

    for msg in messages:
        if len(seeds) >= target_count:
            break
        if isinstance(msg, AIMessage) and hasattr(msg, "content") and isinstance(msg.content, str):
            structured_matches = re.findall(url_title_pattern, msg.content, re.IGNORECASE)
            for url, title, relevance in structured_matches:
                url = url.rstrip('.,;:)*]>').lstrip('(')
                if '**' in url or not url.startswith('http'):
                    continue
                if len(seeds) >= target_count:
                    break
                if url not in [s.url for s in seeds]:
                    seeds.append(CollectedSeed(
                        url=url,
                        title=title.strip(' *:'),
                        relevance_reason=relevance.strip(' *:')[:200],
                    ))

    # Fallback: if no structured matches, extract plain URLs from any message
    if not seeds:
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]\n]+)'
        for msg in messages:
            if len(seeds) >= target_count:
                break
            if hasattr(msg, "content") and isinstance(msg.content, str):
                for match in re.finditer(url_pattern, msg.content):
                    url = match.group(1).rstrip('.,;:)*]>').lstrip('(')
                    if '**' in url or not url.startswith('http'):
                        continue
                    if len(seeds) >= target_count:
                        break
                    if url not in [s.url for s in seeds]:
                        seeds.append(CollectedSeed(
                            url=url,
                            title="",
                            relevance_reason=category,
                        ))

    return CollectionResult(
        category=category,
        seeds=seeds,
        search_count=search_count,
        notes=f"Collected {len(seeds)} seeds in {search_count} searches",
    )


async def collect_seeds(
    categories: list[str] | None = None,
    target_per_category: int = 8,
    validate: bool = True,
) -> dict[str, list[dict]]:
    """Collect seeds for multiple categories.

    Args:
        categories: List of category names, or None for all
        target_per_category: Target seeds per category
        validate: Whether to validate URLs after collection

    Returns:
        Dict mapping category to list of validated seed dicts
    """
    _ensure_tracing_config()

    if categories is None:
        categories = list(TOPIC_CATEGORIES.keys())

    results = {}
    existing_urls: set[str] = set()

    for category in categories:
        print(f"Collecting seeds for: {category}")

        try:
            result = await collect_seeds_for_category(
                category=category,
                target_count=target_per_category,
            )

            validated_seeds = []
            for seed in result.seeds:
                if validate:
                    validation = await validate_url(seed.url, existing_urls)
                    if validation["valid"]:
                        existing_urls.add(validation["normalized_url"])
                        validated_seeds.append({
                            "url": validation["normalized_url"],
                            "title": seed.title,
                            "category": category,
                            "relevance": seed.relevance_reason,
                        })
                    else:
                        print(f"  Skipped (invalid): {seed.url} - {validation['reason']}")
                else:
                    validated_seeds.append({
                        "url": seed.url,
                        "title": seed.title,
                        "category": category,
                        "relevance": seed.relevance_reason,
                    })

            results[category] = validated_seeds
            print(f"  Found {len(validated_seeds)} valid seeds (from {len(result.seeds)} raw)")

        except Exception as e:
            print(f"  Error collecting for {category}: {e}")
            results[category] = []

    return results
