"""LangSmith-native evaluators for evaluate_existing() integration.

All evaluators follow signature: (run: Run, example: Example | None) -> dict
Results appear in LangSmith dashboard.

Two categories:
1. Adapted output evaluators (from expansion_evaluators.py)
2. Trajectory evaluators (using agentevals)
"""

from __future__ import annotations

import json
from typing import Any

from .expansion_evaluators import _get_llm_judge


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _collect_tool_calls_recursive(child_runs: list | None) -> list:
    """Recursively collect all tool runs from nested child_runs.

    LangGraph nests tool calls inside "tools" chain runs.
    This function traverses the full tree to find all tool runs.
    """
    if not child_runs:
        return []

    tool_calls = []
    for run in child_runs:
        run_type = getattr(run, "run_type", "")
        if run_type == "tool":
            tool_calls.append(run)
        # Recursively search nested children
        nested = getattr(run, "child_runs", None)
        if nested:
            tool_calls.extend(_collect_tool_calls_recursive(nested))

    return tool_calls


def _extract_expansion_from_messages(messages: list) -> dict | None:
    """Extract expansion JSON from LangGraph message history.

    The agent outputs expansion as a JSON block in its final message.
    """
    for msg in reversed(messages):
        content = (
            msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        )
        if isinstance(content, str) and "```json" in content and '"source_summary"' in content:
            try:
                json_str = content.split("```json")[1].split("```")[0]
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                continue
    return None


def _get_outputs_from_run(run: Any) -> dict:
    """Extract outputs dict from a LangSmith run.

    Handles both direct outputs and LangGraph message-based outputs.
    """
    outputs = getattr(run, "outputs", None) or {}

    # Handle LangGraph structure with messages
    if "messages" in outputs:
        expansion_data = _extract_expansion_from_messages(outputs["messages"])
        if expansion_data:
            return expansion_data

    return outputs


def _get_inputs_from_run(run: Any, example: Any | None) -> dict:
    """Extract inputs from run or example."""
    if example and hasattr(example, "inputs"):
        return example.inputs
    return getattr(run, "inputs", None) or {}


def _extract_fetched_content(run: Any) -> list[str]:
    """Extract content from fetch tool outputs for groundedness verification.

    Returns list of content strings from fetch_url, github_repo, web_search outputs.
    """
    child_runs = getattr(run, "child_runs", None) or []
    tool_calls = _collect_tool_calls_recursive(child_runs)

    fetched_content = []
    fetch_tools = {"fetch_url", "fetch_tweet", "web_search", "github_repo"}

    for tc in tool_calls:
        tool_name = getattr(tc, "name", "")
        if tool_name in fetch_tools:
            outputs = getattr(tc, "outputs", None)
            if outputs:
                # Extract content from various output formats
                content = None
                if isinstance(outputs, dict):
                    content = outputs.get("content") or outputs.get("output") or str(outputs)
                elif isinstance(outputs, str):
                    content = outputs
                else:
                    content = str(outputs)

                if content and len(content) > 50:  # Skip empty/tiny outputs
                    # Truncate very long content to avoid token limits
                    if len(content) > 2000:
                        content = content[:2000] + "... [truncated]"
                    fetched_content.append(f"[{tool_name}]: {content}")

    return fetched_content


def _format_trajectory_for_agentevals(run: Any) -> list[dict]:
    """Convert LangSmith run with child_runs to agentevals trajectory format.

    agentevals expects OpenAI-style messages:
    [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "", "tool_calls": [...]},
        {"role": "tool", "content": "..."},
    ]
    """
    trajectory = []

    # Add initial user message from inputs
    inputs = getattr(run, "inputs", None) or {}
    if inputs:
        user_content = inputs.get("content", "") or str(inputs)
        trajectory.append({"role": "user", "content": user_content})

    # Process tool calls - use recursive collector for LangGraph nested structure
    child_runs = getattr(run, "child_runs", None) or []
    tool_calls = _collect_tool_calls_recursive(child_runs)

    for i, tc in enumerate(tool_calls):
        # Generate stable tool_call_id from run id or index
        run_id = str(getattr(tc, "id", "")) or str(i)
        tool_call_id = f"call_{run_id[:8]}"

        # Tool call from assistant (OpenAI format)
        tool_name = getattr(tc, "name", "unknown")
        tool_inputs = getattr(tc, "inputs", None) or {}
        tool_call = {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(tool_inputs),
            }
        }
        trajectory.append(
            {"role": "assistant", "content": "", "tool_calls": [tool_call]}
        )

        # Tool result with matching tool_call_id
        tool_outputs = getattr(tc, "outputs", None)
        trajectory.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(tool_outputs) if tool_outputs else ""
        })

    # Add final assistant response
    outputs = getattr(run, "outputs", None) or {}
    if "messages" in outputs:
        messages = outputs["messages"]
        if messages:
            last_msg = messages[-1]
            final_content = (
                last_msg.get("content", "")
                if isinstance(last_msg, dict)
                else str(last_msg)
            )
            trajectory.append({"role": "assistant", "content": final_content})

    return trajectory


# ============================================================
# ADAPTED OUTPUT EVALUATORS (LangSmith-compatible)
# ============================================================


def structure_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible structure evaluator.

    Checks if run outputs have required expansion fields.
    Note: Empty lists/strings are valid (e.g., no key_points extracted).
    Only missing fields or None values fail.
    """
    outputs = _get_outputs_from_run(run)

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


def efficiency_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible efficiency evaluator.

    Requires load_nested=True to access child_runs.

    Scoring:
    - No tool calls at all: 0.5 (not ideal but may be valid for simple expansions)
    - Zero redundant calls: 1.0 (optimal)
    - Redundant calls: penalized proportionally
    """
    child_runs = getattr(run, "child_runs", None)
    if child_runs is None:
        return {
            "metric_name": "efficiency",
            "score": None,
            "error": "child_runs not loaded - ensure load_nested=True",
            "tool_calls": 0,
            "redundant": 0,
            "efficient": False,
        }

    # Use recursive collector because LangGraph nests tools inside chain runs
    tool_calls = _collect_tool_calls_recursive(child_runs)

    # No tool calls - neutral score (may be valid for some inputs)
    if not tool_calls:
        return {
            "metric_name": "efficiency",
            "score": 0.5,  # Neutral - no evidence of inefficiency OR efficiency
            "tool_calls": 0,
            "redundant": 0,
            "efficient": True,  # No redundancy by definition
        }

    # Check for redundant patterns
    redundant = 0
    urls_fetched: set[str] = set()

    for tc in tool_calls:
        tool_name = getattr(tc, "name", "")
        tool_inputs = getattr(tc, "inputs", None) or {}

        if tool_name in ["fetch_url", "github_repo"]:
            url = tool_inputs.get("url") or ""
            if tool_name == "github_repo":
                owner = tool_inputs.get("owner", "")
                repo = tool_inputs.get("repo", "")
                url = f"github.com/{owner}/{repo}"

            if url and url in urls_fetched:
                redundant += 1
            urls_fetched.add(url)

    return {
        "metric_name": "efficiency",
        "score": 1 - (redundant / len(tool_calls)),
        "tool_calls": len(tool_calls),
        "redundant": redundant,
        "efficient": redundant == 0,
    }


def sources_retrieved_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible sources retrieved evaluator.

    Requires load_nested=True to access child_runs.
    Returns error if child_runs not available.
    """
    child_runs = getattr(run, "child_runs", None)
    if child_runs is None:
        return {
            "metric_name": "sources_retrieved",
            "score": None,
            "error": "child_runs not loaded - ensure load_nested=True",
            "pass": False,
        }

    # Use recursive collector because LangGraph nests tools inside chain runs
    tool_calls = _collect_tool_calls_recursive(child_runs)

    fetch_tools = {"fetch_url", "fetch_tweet", "web_search", "github_repo"}
    retrieved = any(getattr(tc, "name", "") in fetch_tools for tc in tool_calls)

    return {
        "metric_name": "sources_retrieved",
        "score": 1.0 if retrieved else 0.0,
        "pass": retrieved,
    }


# ============================================================
# MODEL-BASED OUTPUT EVALUATORS (LangSmith-compatible)
# ============================================================

_groundedness_judge = None
_coverage_judge = None
_authority_judge = None
_topic_judge = None


def groundedness_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible groundedness evaluator.

    Extracts fetched content from tool outputs to enable verification.
    """
    global _groundedness_judge
    if _groundedness_judge is None:
        _groundedness_judge = _get_llm_judge(
            prompt="""Evaluate if the expansion's claims are grounded in the retrieved source content.

Compare the expansion outputs against the fetched source content to verify claims.

Expansion outputs (claims to verify):
{outputs}

Score 1-5:
5: All claims traceable to fetched sources, no hallucination
4: Most claims grounded, minor unsupported details
3: Mix of grounded and speculative claims
2: Significant claims lack source support
1: Appears to hallucinate or fabricate information

Explain which specific claims lack grounding in the fetched content."""
        )

    outputs = _get_outputs_from_run(run)

    # Extract fetched content from tool outputs for verification
    fetched_content = _extract_fetched_content(run)
    if fetched_content:
        outputs = dict(outputs)  # Copy to avoid mutation
        outputs["_fetched_sources"] = "\n\n".join(fetched_content)
    inputs = _get_inputs_from_run(run, example)

    result = _groundedness_judge(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "groundedness"}


def coverage_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible coverage evaluator."""
    global _coverage_judge
    if _coverage_judge is None:
        _coverage_judge = _get_llm_judge(
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

    outputs = _get_outputs_from_run(run)
    inputs = _get_inputs_from_run(run, example)

    result = _coverage_judge(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "coverage"}


def authority_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible authority evaluator."""
    global _authority_judge
    if _authority_judge is None:
        _authority_judge = _get_llm_judge(
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

    outputs = _get_outputs_from_run(run)
    inputs = _get_inputs_from_run(run, example)

    result = _authority_judge(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "authority"}


def topic_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible topic quality evaluator."""
    global _topic_judge
    if _topic_judge is None:
        _topic_judge = _get_llm_judge(
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

    outputs = _get_outputs_from_run(run)
    inputs = _get_inputs_from_run(run, example)

    result = _topic_judge(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "topic_quality"}


# ============================================================
# TRAJECTORY EVALUATORS (using agentevals)
# ============================================================

_tool_efficiency_evaluator = None
_reasoning_quality_evaluator = None
_goal_completion_evaluator = None


def _get_trajectory_evaluator(prompt: str, model: str = "anthropic:claude-sonnet-4-20250514"):
    """Create a trajectory LLM-as-judge evaluator. Requires agentevals."""
    try:
        from agentevals.trajectory.llm import create_trajectory_llm_as_judge

        return create_trajectory_llm_as_judge(
            prompt=prompt,
            model=model,
            continuous=True,
        )
    except ImportError:

        def stub(outputs: list[dict]) -> dict:
            return {
                "score": None,
                "error": "agentevals not installed - run: pip install agentevals",
            }

        return stub


def trajectory_tool_efficiency(run: Any, example: Any | None) -> dict:
    """Evaluate agent's tool usage efficiency.

    Checks for:
    - Redundant tool calls (same URL fetched twice)
    - Unnecessary fetches (fetching when data already available)
    - Optimal tool ordering
    """
    global _tool_efficiency_evaluator
    if _tool_efficiency_evaluator is None:
        _tool_efficiency_evaluator = _get_trajectory_evaluator(
            prompt="""Evaluate the agent's tool usage efficiency in this research task.

<trajectory>
{outputs}
</trajectory>

Consider:
1. Redundancy: Did the agent call the same tool with same inputs multiple times?
2. Necessity: Were all tool calls necessary, or could some be avoided?
3. Ordering: Did the agent fetch primary source first before searching?
4. Early stopping: Did agent stop searching once it had sufficient information?

Score 1-5:
5: Optimal tool usage - no redundancy, all calls necessary, good ordering
4: Minor inefficiency - 1-2 unnecessary calls but generally efficient
3: Moderate inefficiency - some redundant calls or poor ordering
2: Significant waste - multiple redundant calls or clearly unnecessary fetches
1: Very inefficient - excessive tool calls, repeated fetches, no strategy

Explain specific inefficiencies observed."""
        )

    trajectory = _format_trajectory_for_agentevals(run)
    result = _tool_efficiency_evaluator(outputs=trajectory)
    return {**result, "metric_name": "trajectory_tool_efficiency"}


def trajectory_reasoning_quality(run: Any, example: Any | None) -> dict:
    """Evaluate the quality of agent's decision-making throughout execution.

    Checks:
    - Search strategy quality
    - Source evaluation
    - Adaptation based on results
    - Synthesis across sources
    """
    global _reasoning_quality_evaluator
    if _reasoning_quality_evaluator is None:
        _reasoning_quality_evaluator = _get_trajectory_evaluator(
            prompt="""Evaluate the agent's reasoning and decision-making quality.

<trajectory>
{outputs}
</trajectory>

Consider:
1. Search strategy: Did agent formulate good search queries?
2. Source evaluation: Did agent prioritize authoritative sources?
3. Adaptation: Did agent adjust strategy based on results?
4. Synthesis: Did agent connect information across sources?
5. Completeness: Did agent gather sufficient information before concluding?

Score 1-5:
5: Excellent reasoning - strategic, adaptive, thorough
4: Good reasoning - mostly sound decisions with minor issues
3: Adequate reasoning - gets the job done but missed opportunities
2: Weak reasoning - poor queries, ignored relevant results
1: Poor reasoning - random tool calls, no clear strategy

Explain the reasoning patterns observed."""
        )

    trajectory = _format_trajectory_for_agentevals(run)
    result = _reasoning_quality_evaluator(outputs=trajectory)
    return {**result, "metric_name": "trajectory_reasoning"}


def trajectory_goal_completion(run: Any, example: Any | None) -> dict:
    """Evaluate whether agent accomplished the research task.

    Checks if the agent produced:
    - Accurate source comprehension
    - Meaningful key insights
    - Valuable related items
    - Actionable assessment
    """
    global _goal_completion_evaluator
    if _goal_completion_evaluator is None:
        _goal_completion_evaluator = _get_trajectory_evaluator(
            prompt="""Evaluate whether the agent accomplished the research goal.

<trajectory>
{outputs}
</trajectory>

The agent was asked to expand a seed (URL, idea, or question) into:
- Source summary
- Key points
- Related items (2-4 high-quality)
- Assessment
- Topics

Consider:
1. Source comprehension: Did agent accurately understand the source?
2. Key insight extraction: Are key points meaningful, not generic?
3. Related discovery: Did agent find genuinely related, valuable items?
4. Assessment quality: Is assessment specific and actionable?

Score 1-5:
5: Fully accomplished - comprehensive, insightful expansion
4: Mostly accomplished - good expansion with minor gaps
3: Partially accomplished - basic expansion, missed opportunities
2: Weakly accomplished - shallow or missing key elements
1: Failed - did not produce useful expansion

What aspects were handled well or poorly?"""
        )

    trajectory = _format_trajectory_for_agentevals(run)
    result = _goal_completion_evaluator(outputs=trajectory)
    return {**result, "metric_name": "trajectory_goal_completion"}


# ============================================================
# EVALUATOR COLLECTIONS
# ============================================================

# Code-based evaluators (fast, no API calls)
CODE_EVALUATORS = [
    structure_evaluator_ls,
    efficiency_evaluator_ls,
    sources_retrieved_evaluator_ls,
]

# Model-based output evaluators (require API calls via openevals)
OUTPUT_EVALUATORS = [
    groundedness_evaluator_ls,
    coverage_evaluator_ls,
    authority_evaluator_ls,
    topic_evaluator_ls,
]

# Trajectory evaluators (require API calls via agentevals)
TRAJECTORY_EVALUATORS = [
    trajectory_tool_efficiency,
    trajectory_reasoning_quality,
    trajectory_goal_completion,
]

# All evaluators combined
ALL_EVALUATORS = CODE_EVALUATORS + OUTPUT_EVALUATORS + TRAJECTORY_EVALUATORS
