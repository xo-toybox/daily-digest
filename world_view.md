# Agent World Model

> This document grounds the agent in temporal and epistemic context. Updated each session with synthesized insights.

## Temporal Anchor

**Session Date:** 2026-01-11

**Field Velocity Acknowledgment:**
The generative AI landscape evolves at a pace where:
- Weekly: New model releases, benchmark updates
- Monthly: Architectural variations, tooling shifts
- Quarterly: Paradigm-level changes possible

**Implication:** Content dated beyond 3 months warrants verification against more recent sources before synthesis.

---

## Active Landscape

> Populated with verified observations from research sessions.

### What Appears Settled

- **Context management is the core challenge in production agents** — Practitioner synthesis (Lance Martin), corroborated by multiple implementations — As of 2026-01
- **Traces replace code as primary documentation for AI apps** — Technical blog (LangChain) + ecosystem tooling (LangSmith, RagaAI) — As of 2026-01
- **Small eval datasets (20-50 tasks) are sufficient for early development** — Official docs (Anthropic engineering) — As of 2026-01
- **Multi-layer grading (code + LLM + human) is the standard for agent eval** — Official docs (Anthropic) — As of 2026-01

### What Remains Contested

- **Optimal tool count for agents**: "Few atomic tools + computer delegation" (Claude Code pattern) vs "Rich domain-specific toolsets" (traditional approach)
  - Note: Both valid depending on agent autonomy level and task complexity

- **Context caching vs. context compression**: Trade-off between cost efficiency (caching) and maximum utilization (compression)
  - Note: May converge with learned context management

### What's Moving Fast

- **MCP (Model Context Protocol) ecosystem** — Last verified: 2026-01-11 — Expect rapid drift
- **Agent evaluation benchmarks** — Last verified: 2026-01-11 — New benchmarks emerging frequently
- **Sub-agent coordination patterns** — Last verified: 2026-01-11 — Active experimentation phase

---

## Source Epistemology

When evaluating claims encountered during search, apply these lenses:

| Pattern | Indicators | Handling |
|---------|------------|----------|
| **Likely false** | Contradicts multiple verified sources; no credible corroboration | Discard. Note if recurring. |
| **Insight in wrong context** | Core idea has merit; framing mismatched | Extract principle. Recontextualize. |
| **Valid but scenario-bound** | Works in stated context; contradicts others also valid in theirs | Present divergence with conditions. |
| **True but low-density** | Accurate; widely known; no novel insight | Deprioritize unless needed for grounding. |
| **Emerging signal** | Multiple independent sources converging | High priority for synthesis. Flag explicitly. |

---

## Corroboration Standards

### What Counts as Independent Corroboration

- Sources must not cite each other or a common upstream source
- Practitioner experience + benchmark data > multiple blog posts echoing one paper

### Source Weighting Guidance

| Source Type | Weight | Notes |
|-------------|--------|-------|
| Peer-reviewed paper | High | Strong for foundational claims |
| Official documentation | High | Best for implementation details |
| Technical blog (known practitioner) | Medium-High | Good for practical patterns |
| Social media threads | Medium | Good for emerging signals, verify claims |
| Aggregator/news coverage | Low | Use for discovery, not verification |
| Benchmark leaderboards | Medium | Context-dependent, check methodology |

---

## Known Blind Spots

> Areas where the agent's base knowledge is likely stale or underspecified.

- **Proprietary agent internals** — Why: Claude Code, Manus, etc. implementation details not public
- **Real-time benchmark standings** — Why: Leaderboards change frequently
- **Pricing/cost comparisons** — Why: Model pricing changes without notice

---

## Synthesized Themes (Cross-Session)

> High-level patterns emerging across multiple research sessions.

### Theme: Agent Architecture Convergence

**Observation:** Successful production agents (Claude Code, Manus) share common patterns:
1. Few atomic tools (~12-20) delegating to computer primitives
2. Progressive disclosure over upfront tool loading
3. Context offloading to filesystem
4. Sub-agent isolation for parallelization

**Confidence:** High (multiple independent practitioner reports + acquisition signals)

### Theme: Observability as First-Class Concern

**Observation:** AI application development is shifting from code-centric to trace-centric workflows:
1. Traces become primary documentation
2. Debugging = analyzing reasoning chains
3. Evaluation = trace inspection
4. Collaboration = shared observability platforms

**Confidence:** High (convergent tooling from LangChain, Anthropic, independent projects)

### Theme: Eval-Driven Development Emerging

**Observation:** Building evaluations before capabilities is becoming standard practice:
1. Start with real failure cases (20-50 sufficient)
2. Capability evals vs regression evals serve different purposes
3. Three-layer grading addresses non-determinism

**Confidence:** Medium-High (Anthropic official guidance, limited external validation yet)

---

## Update Log

| Date | Section | Change | Reason |
|------|---------|--------|--------|
| 2026-01-11 | Initial | Created document from Iteration 1 findings | First synthesis pass |
| 2026-01-11 | Active Landscape | Populated settled/contested/moving sections | Based on 3 source expansions |
| 2026-01-11 | Synthesized Themes | Added 3 cross-cutting themes | Pattern extraction from digest |
