"""Evaluators for digest synthesis quality.

All model-based (LLM-as-judge) since digest quality is inherently subjective.
"""


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


# Lazy initialization
_connection_evaluator = None
_actionability_evaluator = None
_synthesis_evaluator = None


def connection_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate if cross-connections are insightful vs obvious."""
    global _connection_evaluator
    if _connection_evaluator is None:
        _connection_evaluator = _get_llm_judge(
            prompt="""Evaluate if cross-connections are insightful vs obvious.

Expansions processed: {inputs[expansion_summaries]}
Cross-connections identified: {outputs[cross_connections]}

Score 1-5:
5: Connections reveal non-obvious relationships
3: Connections are logical but surface-level
1: Connections are trivial or missing"""
        )
    result = _connection_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "connections"}


def actionability_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate if open threads are actionable research questions."""
    global _actionability_evaluator
    if _actionability_evaluator is None:
        _actionability_evaluator = _get_llm_judge(
            prompt="""Evaluate if open threads are actionable research questions.

Open threads: {outputs[open_threads]}

Score 1-5:
5: Clear next steps, specific questions to investigate
3: General directions but vague
1: Too abstract to act on"""
        )
    result = _actionability_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "actionability"}


def synthesis_evaluator(inputs: dict, outputs: dict) -> dict:
    """Evaluate overall synthesis quality - the key digest evaluator."""
    global _synthesis_evaluator
    if _synthesis_evaluator is None:
        _synthesis_evaluator = _get_llm_judge(
            prompt="""Evaluate overall synthesis quality.

Input expansions: {inputs[expansion_count]} items
Digest entries: {outputs[entries]}
Cross-connections: {outputs[cross_connections]}
Open threads: {outputs[open_threads]}

Is the digest:
- More than sum of parts? (synthesis vs summarization)
- Specific not generic?
- Worth the compute spent?

Score 1-5 with explanation."""
        )
    result = _synthesis_evaluator(inputs=inputs, outputs=outputs)
    return {**result, "metric_name": "synthesis"}
