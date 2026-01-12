# Ralph Loop 2: Eval & Observability

Read and update tracking at `.ralph/IMPROVEMENTS-eval-framework.md`.
Reference specs: `docs/observability.md`, `docs/observability-impl.md`.

## Core Loop

Run trajectory evaluators against real expansions:

```bash
# Evaluate recent traced runs with trajectory analysis
daily-digest eval --recent --trajectory --limit 10

# Evaluate specific LangSmith experiment (results in dashboard)
daily-digest eval --experiment "expansion-v1" --trajectory --model-based

# Local evaluation on disk (original mode)
daily-digest eval --model-based
```

Iterate until evaluators produce reliable, discriminating quality signals.

## Evaluation Modes

### 1. Code-based (fast, no API calls)
- `structure` - required fields present
- `efficiency` - no redundant tool calls
- `sources_retrieved` - agent fetched sources

### 2. Model-based output (costs API calls via openevals)
- `groundedness` - claims traceable to sources
- `coverage` - captures essential insights
- `authority` - related items from authoritative sources
- `topic_quality` - semantic groupings vs keywords

### 3. Trajectory (costs API calls via agentevals)
- `trajectory_tool_efficiency` - redundant calls, unnecessary fetches, optimal ordering
- `trajectory_reasoning_quality` - search strategy, source evaluation, adaptation
- `trajectory_goal_completion` - did agent produce useful expansion?

## Calibration Checklist

**For output evaluators:**
- Is the rubric clear enough to score consistently?
- Does the score distribution discriminate (not all 3s)?
- Does a failing score suggest what to fix?

**For trajectory evaluators:**
- Does tool_efficiency catch actual redundant calls?
- Does reasoning_quality correlate with expansion quality?
- Does goal_completion match human judgment?

## Reviewer Guidance

Deploy 2 parallel reviewer subagents:

**Evaluator Quality Reviewer:** Attacks evaluators themselves:
- Run on 10+ expansions, check score distribution
- Try to find cases where score doesn't match quality
- Verify trajectory evaluators detect actual issues

**Implementation Completeness Reviewer:** Cross-references spec vs code:
- Are all evaluators callable via CLI?
- Does evaluate_existing() work end-to-end?
- Are results visible in LangSmith dashboard?

**Reviewer calibration:** Reviewers must be ruthless. Surface at least 3-5 concrete improvements per review. Ask: "Would I trust this evaluator to catch a regression?" and "Does this implementation actually work end-to-end?" Vague praise is useless. Specific critiques with proposed fixes are valuable.

## Exit Criteria

Stop when:
1. All evaluators discriminate and correlate with subjective quality
2. Trajectory evaluators catch real agent behavior issues
3. Results appear correctly in LangSmith dashboard
4. pass@k variance < 0.2
5. Remaining issues are low value/effort

When done, run simplification pass (remove dead code, consolidate patterns).

## Key Files

- `src/daily_digest/eval/langsmith_evaluators.py` - LangSmith-compatible evaluators + trajectory evaluators
- `src/daily_digest/eval/langsmith_runner.py` - evaluate_existing() wrapper
- `src/daily_digest/eval/expansion_evaluators.py` - original evaluators
- `src/daily_digest/eval/runner.py` - local evaluation runner
