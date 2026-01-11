"""Seed input collection for eval dataset.

Collects, validates, and scores URLs for evaluation dataset building.
Uses topic categories from docs/topic-taxonomy.md.
"""

import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode

import httpx


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

Return score and brief reasoning.""",
            model="claude-sonnet-4-20250514",
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

    result = _quality_scorer(
        inputs={"url": url, "metadata": metadata, "category": category},
        outputs={},
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
            # Convert to inbox item format
            item = {
                "item_type": "url",
                "content": seed["url"],
                "note": seed.get("metadata", ""),
                "category": seed.get("category"),
                "quality_score": seed.get("score"),
            }
            f.write(json.dumps(item) + "\n")

    return len(seeds)
