# Ralph Loop 2: Eval & Observability

Read and update tracking at `.ralph/EVAL_IMPROVEMENTS.md`.
Reference specs: `docs/observability.md` (design), `docs/observability-impl.md` (implementation).

## Core Loop

Run the eval framework against real expansions. Iterate until evaluators produce reliable, discriminating quality signals.

- Verify implementation matches spec (all 4 steps).
- Test each evaluator for calibration: Does high score = high quality? Does low score tell you what to fix?
- Run pass@k (k=3) to measure non-determinism. Variance > 0.2 is a problem.
- Validate LangSmith integration (traces appear, datasets work).

## Reviewer Guidance

Deploy 2 parallel reviewer subagents:

**Evaluator Quality Reviewer:** Attacks the evaluators themselves. For each:
- Is the rubric clear enough to score consistently?
- Does the score distribution discriminate (not all 3s)?
- Does a failing score suggest what to fix?

**Implementation Completeness Reviewer:** Cross-references spec vs code:
- What's in spec but missing from implementation?
- What's implemented but doesn't work?
- What's undocumented or drift from spec?

**Reviewer calibration:** Reviewers must be ruthless. Surface at least 3-5 concrete improvements per review. Ask: "Would I trust this evaluator to catch a regression?" and "Does this implementation actually work end-to-end?" Vague praise is useless. Specific critiques with proposed fixes are valuable.

## Exit Criteria

Stop when:
1. All evaluators discriminate and correlate with subjective quality
2. All spec sections have working, tested code
3. pass@k variance < 0.2
4. Remaining issues are low value/effort

When done, run simplification pass (remove dead code, consolidate patterns).
