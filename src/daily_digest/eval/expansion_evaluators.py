"""Evaluators for expansion quality.

Two categories:
1. Code-based evaluators (fast, objective, run first)
2. Model-based evaluators (nuanced, run after code checks pass)
"""

from typing import Any


# ============================================================
# CODE-BASED EVALUATORS (fast, objective, run first)
# ============================================================


def structure_evaluator(inputs: dict, outputs: dict) -> dict:
    """Check if output has required structure.

    Returns score of 1.0 if all required fields present, 0.0 otherwise.
    Note: Empty lists/strings are valid (e.g., no key_points extracted).
    Only missing fields or None values fail.
    """
    required = ["source_summary", "key_points", "related", "topics"]
    # Only fail if field is missing entirely or is None
    # Empty lists/strings are valid (agent may legitimately produce no items)
    missing = [k for k in required if k not in outputs or outputs[k] is None]
    return {
        "metric_name": "structure",
        "score": 1.0 if not missing else 0.0,
        "pass": len(missing) == 0,
        "missing_fields": missing,
    }


def efficiency_evaluator(run: Any, example: Any) -> dict:
    """Evaluate agent tool usage efficiency.

    Checks for redundant tool calls (e.g., fetching same URL twice).
    """
    # Access child runs for tool calls
    tool_calls = []
    if hasattr(run, "child_runs"):
        tool_calls = [c for c in run.child_runs if c.run_type == "tool"]

    turns_used = 0
    if hasattr(run, "outputs") and run.outputs:
        turns_used = run.outputs.get("turn_count", 0)

    # Check for redundant patterns
    redundant = 0
    urls_fetched: set[str] = set()

    for tc in tool_calls:
        tool_name = tc.name if hasattr(tc, "name") else ""
        tool_inputs = tc.inputs if hasattr(tc, "inputs") else {}

        if tool_name in ["fetch_url", "github_repo"]:
            url = tool_inputs.get("url") or ""
            if tool_name == "github_repo":
                owner = tool_inputs.get("owner", "")
                repo = tool_inputs.get("repo", "")
                url = f"github.com/{owner}/{repo}"

            if url and url in urls_fetched:
                redundant += 1
            urls_fetched.add(url)

    total_calls = max(len(tool_calls), 1)
    return {
        "metric_name": "efficiency",
        "score": 1 - (redundant / total_calls),
        "tool_calls": len(tool_calls),
        "turns_used": turns_used,
        "redundant": redundant,
        "efficient": redundant == 0 and turns_used <= 8,
    }


def sources_retrieved_evaluator(run: Any, example: Any) -> dict:
    """Binary check: did agent retrieve any sources?"""
    tool_calls = []
    if hasattr(run, "child_runs"):
        tool_calls = [c for c in run.child_runs if c.run_type == "tool"]

    fetch_tools = {"fetch_url", "fetch_tweet", "web_search", "github_repo"}
    retrieved = any(
        (tc.name if hasattr(tc, "name") else "") in fetch_tools for tc in tool_calls
    )

    return {
        "metric_name": "sources_retrieved",
        "score": 1.0 if retrieved else 0.0,
        "pass": retrieved,
    }


# ============================================================
# MODEL-BASED EVALUATORS (nuanced, run after code checks pass)
# ============================================================

# These use LLM-as-judge via openevals. Import lazily to avoid
# requiring openevals for basic functionality.


def _get_llm_judge(prompt: str, model: str = "claude-sonnet-4-20250514"):
    """Create an LLM-as-judge evaluator. Requires openevals."""
    try:
        from openevals.llm import create_llm_as_judge

        return create_llm_as_judge(prompt=prompt, model=model)
    except ImportError:
        # Return a stub that indicates openevals not installed
        def stub(*args, **kwargs):
            return {
                "score": None,
                "error": "openevals not installed - run: pip install openevals",
            }

        return stub


# Lazy initialization of model-based evaluators
_groundedness_evaluator = None
_coverage_evaluator = None
_authority_evaluator = None
_topic_evaluator = None


def groundedness_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate if the expansion's claims are grounded in retrieved sources."""
    global _groundedness_evaluator
    if _groundedness_evaluator is None:
        _groundedness_evaluator = _get_llm_judge(
            prompt="""Evaluate if the expansion's claims are grounded in retrieved sources.

Expansion outputs:
{outputs}

Score 1-5:
5: All claims traceable to sources, no hallucination
4: Most claims grounded, minor unsupported details
3: Mix of grounded and speculative claims
2: Significant claims lack source support
1: Appears to hallucinate or fabricate information

Explain which specific claims lack grounding."""
        )
    result = _groundedness_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "groundedness"}


def coverage_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate if the expansion captures the essential insights from the source."""
    global _coverage_evaluator
    if _coverage_evaluator is None:
        _coverage_evaluator = _get_llm_judge(
            prompt="""Evaluate if the expansion captures the essential insights from the source.

Inputs (original content/URL):
{inputs}

Expansion outputs:
{outputs}

Score 1-5:
5: Comprehensive - captures all important insights, nothing significant missed
4: Good coverage - main points covered, minor gaps
3: Partial - captures obvious points but misses nuance
2: Shallow - only surface-level extraction
1: Inadequate - misses core content

What important aspects were missed?"""
        )
    result = _coverage_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "coverage"}


def authority_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate if related items come from authoritative sources."""
    global _authority_evaluator
    if _authority_evaluator is None:
        _authority_evaluator = _get_llm_judge(
            prompt="""Evaluate if related items come from authoritative sources.

Expansion outputs:
{outputs}

Score 1-5:
5: All sources are authoritative (official docs, primary authors, established publications)
4: Mostly authoritative with minor exceptions
3: Mix of authoritative and questionable sources
2: Relies heavily on low-authority sources
1: Sources are unreliable or inappropriate

Which sources lack authority and why?"""
        )
    result = _authority_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "authority"}


def topic_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate if topics are semantic groupings (problem spaces) vs keywords."""
    global _topic_evaluator
    if _topic_evaluator is None:
        _topic_evaluator = _get_llm_judge(
            prompt="""Evaluate if topics are semantic groupings (problem spaces) vs keywords.

Good: "building-reliable-ai-systems" (problem space)
Bad: "evals", "testing", "monitoring" (keywords)

Expansion outputs:
{outputs}

Score 1-5:
5: All topics are meaningful semantic groupings (problem spaces or domains)
4: Most topics are semantic, one may be keyword-ish
3: Mix of semantic and keyword-style topics
2: Most topics are keywords, one may be semantic
1: All topics are superficial keywords or too generic"""
        )
    result = _topic_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "topic_quality"}
