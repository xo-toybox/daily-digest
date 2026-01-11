# Agent World Model

> This document grounds the agent in temporal and epistemic context. Update before each session or when significant shifts occur.

## Temporal Anchor

**Session Date:** `[YYYY-MM-DD]`

**Field Velocity Acknowledgment:**
The generative AI landscape evolves at a pace where:
- Weekly: New model releases, benchmark updates
- Monthly: Architectural variations, tooling shifts
- Quarterly: Paradigm-level changes possible

**Implication:** Content dated beyond `[threshold you determine]` warrants verification against more recent sources before synthesis.

---

## Active Landscape

> Populate with verified observations. Each entry should include a rough timestamp and source class (paper, official docs, credible practitioner report, etc.)

### What Appears Settled
<!-- Claims with broad corroboration across independent sources -->

- `[Claim]` — `[Source class]` — `[As of date]`

### What Remains Contested
<!-- Active debates where credible positions diverge -->

- `[Topic]`: `[Position A summary]` vs `[Position B summary]`
  - Note: Both may be valid in different contexts. Surface the divergence.

### What's Moving Fast
<!-- Areas where even recent sources may be outdated -->

- `[Domain]` — Last verified: `[date]` — Expect drift

---

## Source Epistemology

When evaluating claims encountered during search, apply these lenses:

| Pattern | Indicators | Handling |
|---------|------------|----------|
| **Likely false** | Contradicts multiple verified sources; no credible corroboration | Discard. Note if recurring (may indicate persistent misconception worth flagging). |
| **Insight in wrong context** | Core idea has merit; framing or application mismatched | Extract the underlying principle. Recontextualize before including. |
| **Valid but scenario-bound** | Opinion/approach works in stated context; contradicts others who are also valid in *their* context | Do not flatten. Present the divergence and the conditions under which each holds. |
| **True but low-density** | Accurate; widely known; no novel insight | Deprioritize unless needed for corroboration or grounding. |
| **Emerging signal** | Multiple independent sources converging on same observation | High priority for synthesis. Flag explicitly. |

---

## Corroboration Standards

### What Counts as Independent Corroboration
<!-- Define your threshold -->

- Sources must not cite each other or a common upstream source
- Practitioner experience + benchmark data > multiple blog posts echoing one paper

### Source Weighting Guidance

| Source Type | Weight | Notes |
|-------------|--------|-------|
| Peer-reviewed paper | `[High/Medium/Low]` | `[Your reasoning]` |
| Official documentation | | |
| Technical blog (known practitioner) | | |
| Social media threads | | |
| Aggregator/news coverage | | |
| Benchmark leaderboards | | |

---

## Known Blind Spots

> Areas where the agent's base knowledge is likely stale or underspecified. Prioritize search verification here.

- `[Topic]` — Why it's a blind spot: `[reasoning]`

---

## Session-Specific Context

> Optional section for per-run context the curator provides.

**Focus areas for this session:**
<!-- What topics are in scope -->

**Recency requirements:**
<!-- e.g., "Only sources from past 3 months for X topic" -->

**User-specified priors:**
<!-- Any assumptions or framings the curator wants enforced -->

---

## Update Log

| Date | Section | Change | Reason |
|------|---------|--------|--------|
| | | | |