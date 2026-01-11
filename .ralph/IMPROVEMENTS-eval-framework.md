# Eval & Observability Improvements Tracker

Reference: `.ralph/ralph-instruction2.md`

## Format
- **Priority**: Critical/High/Medium/Low
- **Status**: Proposed | In Progress | Completed | Deferred
- **Category**: Evaluator | Integration | CLI | Spec-Drift

---

## Implementation Checklist

- [x] Step 1: Tracing Foundation
- [x] Step 2: Evaluators (10 total)
- [x] Step 3: Dataset Management + pass@k
- [x] Step 4: Seed Collection Pipeline
- [ ] All evaluators calibrated
- [ ] pass@k variance < 0.2
- [ ] LangSmith integration verified

---

## Iteration Log

(Populate during iterations)

---

## Evaluator Calibration

| Evaluator | Discrimination | Calibration | Actionability | Status |
|-----------|----------------|-------------|---------------|--------|
| structure | - | - | - | Untested |
| efficiency | - | - | - | Untested |
| sources_retrieved | - | - | - | Untested |
| groundedness | - | - | - | Untested |
| coverage | - | - | - | Untested |
| authority | - | - | - | Untested |
| topic_quality | - | - | - | Untested |
| connections | - | - | - | Untested |
| actionability | - | - | - | Untested |
| synthesis | - | - | - | Untested |

---

## Known Issues

(Populate during iterations)

---

## Decision Log

| Iteration | Decision | Rationale |
|-----------|----------|-----------|
| 0 | Lazy-load openevals | Avoid hard dep for basic use |
