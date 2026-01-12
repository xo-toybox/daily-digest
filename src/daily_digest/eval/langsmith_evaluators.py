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

    # Process child runs (tool calls and their results)
    child_runs = getattr(run, "child_runs", None) or []
    for child in child_runs:
        if getattr(child, "run_type", "") == "tool":
            # Tool call from assistant
            tool_name = getattr(child, "name", "unknown")
            tool_inputs = getattr(child, "inputs", None) or {}
            tool_call = {
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_inputs),
                }
            }
            trajectory.append(
                {"role": "assistant", "content": "", "tool_calls": [tool_call]}
            )

            # Tool result
            tool_outputs = getattr(child, "outputs", None)
            trajectory.append(
                {"role": "tool", "content": str(tool_outputs) if tool_outputs else ""}
            )

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
    """
    outputs = _get_outputs_from_run(run)

    required = ["source_summary", "key_points", "related", "topics"]
    missing = [k for k in required if k not in outputs or not outputs[k]]

    return {
        "key": "structure",
        "score": 1.0 if not missing else 0.0,
        "pass": len(missing) == 0,
        "missing_fields": missing,
    }


def efficiency_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible efficiency evaluator.

    Requires load_nested=True to access child_runs.
    """
    child_runs = getattr(run, "child_runs", None) or []
    tool_calls = [c for c in child_runs if getattr(c, "run_type", "") == "tool"]

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

    total_calls = max(len(tool_calls), 1)
    return {
        "key": "efficiency",
        "score": 1 - (redundant / total_calls),
        "tool_calls": len(tool_calls),
        "redundant": redundant,
        "efficient": redundant == 0,
    }


def sources_retrieved_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible sources retrieved evaluator.

    Requires load_nested=True to access child_runs.
    """
    child_runs = getattr(run, "child_runs", None) or []
    tool_calls = [c for c in child_runs if getattr(c, "run_type", "") == "tool"]

    fetch_tools = {"fetch_url", "fetch_tweet", "web_search", "github_repo"}
    retrieved = any(getattr(tc, "name", "") in fetch_tools for tc in tool_calls)

    return {
        "key": "sources_retrieved",
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
    """LangSmith-compatible groundedness evaluator."""
    global _groundedness_judge
    if _groundedness_judge is None:
        _groundedness_judge = _get_llm_judge(
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

Explain which specific claims lack grounding."""
        )

    outputs = _get_outputs_from_run(run)
    inputs = _get_inputs_from_run(run, example)

    result = _groundedness_judge(inputs=inputs, outputs=outputs)
    return {"key": "groundedness", **result}


def coverage_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible coverage evaluator."""
    global _coverage_judge
    if _coverage_judge is None:
        _coverage_judge = _get_llm_judge(
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

What important aspects were missed?"""
        )

    outputs = _get_outputs_from_run(run)
    inputs = _get_inputs_from_run(run, example)

    result = _coverage_judge(inputs=inputs, outputs=outputs)
    return {"key": "coverage", **result}


def authority_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible authority evaluator."""
    global _authority_judge
    if _authority_judge is None:
        _authority_judge = _get_llm_judge(
            prompt="""Evaluate if related items come from authoritative sources.

Related Items Found:
{outputs[related]}

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
    return {"key": "authority", **result}


def topic_evaluator_ls(run: Any, example: Any | None) -> dict:
    """LangSmith-compatible topic quality evaluator."""
    global _topic_judge
    if _topic_judge is None:
        _topic_judge = _get_llm_judge(
            prompt="""Evaluate if topics are semantic groupings (problem spaces) vs keywords.

Good: "building-reliable-ai-systems" (problem space)
Bad: "evals", "testing", "monitoring" (keywords)

Topics: {outputs[topics]}
Content Summary: {outputs[source_summary]}

Score 1-5:
5: All topics are meaningful semantic groupings
3: Mix of semantic and keyword-style
1: All topics are superficial keywords"""
        )

    outputs = _get_outputs_from_run(run)
    inputs = _get_inputs_from_run(run, example)

    result = _topic_judge(inputs=inputs, outputs=outputs)
    return {"key": "topic_quality", **result}


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
    return {"key": "trajectory_tool_efficiency", **result}


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
    return {"key": "trajectory_reasoning", **result}


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
    return {"key": "trajectory_goal_completion", **result}


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
