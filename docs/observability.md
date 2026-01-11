# Observability & Evaluation Design

## Overview

Replace custom `TrajectoryLogger` with LangSmith for tracing, monitoring, and evaluation. Focus: **expansion quality → digest synthesis pipeline**.

## Core Principles

> "In AI agents, code is scaffolding while actual decision-making occurs at runtime inside the model. Traces are the source of truth." — [LangChain](https://blog.langchain.com/in-software-the-code-documents-the-app-in-ai-the-traces-do/)

> "Don't trust eval scores without digging into the details. The infrastructure matters less than whether your eval actually measures what you care about." — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

**Key shifts:**
1. **Traces replace code review** — Debug by examining traces, not stepping through code
2. **Multi-grader approach** — Layer code-based, model-based, and human evaluators
3. **Continuous eval from production** — Traces naturally create labeled datasets
4. **Embrace non-determinism** — Measure pass@k (any of k runs succeeds) not just single-run

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         LangSmith                               │
├─────────────────────────────────────────────────────────────────┤
│  Tracing              │  Evaluation           │  Monitoring     │
│  ────────             │  ──────────           │  ──────────     │
│  @traceable decorator │  Datasets (golden)    │  Dashboards     │
│  LangChain auto-trace │  Custom evaluators    │  Alerts         │
│  Metadata/tags        │  LLM-as-judge         │  Token usage    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Tracing Strategy

### Integration Points

| Component | Current | With LangSmith |
|-----------|---------|----------------|
| `agent.py` | LangGraph + TrajectoryLogger | LangGraph auto-traces when LANGCHAIN_TRACING_V2=true |
| `digest.py` | Direct anthropic SDK | Wrap with @traceable |
| `tools.py` | Tool functions | @traceable on implementations |
| `cli.py` | TrajectoryLogger lifecycle | Configure project, optional local export |

### Key Decisions
- LangGraph traces automatically when env vars set
- Direct Anthropic SDK calls need explicit @traceable wrapper
- Keep optional local JSON export for offline dev analysis

---

## Phase 2: Evaluation Strategy

### Multi-Grader Approach

Layer evaluators for robustness (per [Anthropic guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)):

| Grader Type | Strengths | Use For |
|-------------|-----------|---------|
| **Code-based** | Fast, objective, deterministic | Binary checks (task completed, sources retrieved, JSON valid) |
| **Model-based** | Handles nuance, open-ended | Quality dimensions (accuracy, relevance, synthesis) |
| **Human** | Gold standard calibration | Calibrating model graders, edge cases, periodic audits |

**Calibration requirement**: Periodically test model-based graders against human judgment on a gold sample. Eval drift is real.

### Quality Chain

```
Expansion Quality ──────► Digest Quality
     ▲                         ▲
     │                         │
┌────┴────┐              ┌─────┴─────┐
│Evaluators│              │Evaluators │
├─────────┤              ├───────────┤
│Groundedness│           │Connections│
│Coverage    │           │Actionable │
│Authority   │           │Synthesis  │
│Efficiency  │           │           │
└─────────┘              └───────────┘
```

### Research Agent-Specific Evaluators

| Evaluator | What it measures | Why it matters |
|-----------|------------------|----------------|
| **Groundedness** | Are claims supported by retrieved sources? | Prevents hallucinated insights |
| **Coverage** | Did agent extract mandatory facts/insights? | Ensures comprehensive expansion |
| **Authority** | Did agent prioritize authoritative sources? | Quality over accessibility |
| **Efficiency** | Tool calls, turns used, redundancy | Cost and latency control |

### Non-Determinism Metrics

Agents may find valid insights via different reasoning paths. Track:

- **pass@k**: At least one correct solution across k runs (capability ceiling)
- **pass^k**: All k runs correct (consistency floor)
- **Variance**: How much do outputs differ across identical inputs?

### Dataset Structure

**Expansion Dataset** — inputs map to InboxItem, outputs map to Expansion:
- `inputs`: {item_type, content, note}
- `outputs`: {source_summary, key_points, related, topics}
- `metadata`: {quality_tier, date_added}

**Digest Dataset** — inputs are expansions, outputs are digest:
- `inputs`: {expansions[]}
- `outputs`: {cross_connections, open_threads, entries}

### Dataset Bootstrapping Strategy

> "Start with 20-50 realistic test cases from actual failures, not generic synthetics." — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

1. **Failure-first**: Prioritize cases where the agent failed or produced poor output
2. **Real inputs**: Use actual URLs/ideas users submitted, not synthetic examples
3. **Balanced sets**: Include cases where behavior should AND shouldn't occur
4. **Expert agreement**: Only include cases where domain experts would independently agree on quality

**Continuous growth:**
- Production traces naturally create labeled datasets
- Weekly: Review 5-10 random traces, add interesting cases
- On failure: Always add to dataset with root cause annotation

---

## Seed Input Collection Pipeline

Before we can evaluate expansions, we need quality seed inputs. Uses [DeepAgents](https://github.com/langchain-ai/deepagents) for bounded exploration with human-in-the-loop approval.

### Quality Tier Promotion

```
Synthetic (auto-discovered via web search)
    │
    ▼ Code validation (accessible, not duplicate, schema valid)
Silver (validated structure, untested quality)
    │
    ▼ AI scoring (score >= 3 passes, < 3 auto-rejected)
Silver+ (AI-approved candidates)
    │
    ▼ Human review in LangSmith Annotation Queue
Gold (human-verified, ready for eval)
    │
    ▼ Transform to inbox.json shape
Eval Input (grouped by category/difficulty)
```

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│              SEED INPUT COLLECTION (DeepAgents + LangSmith)             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. EXPLORATION (DeepAgents with subagents)                             │
│     ├── Main agent: coordinates search across topic categories          │
│     ├── Subagents: one per topic, bounded web_search only               │
│     ├── interrupt_on: review before adding to candidate pool            │
│     └── Deduplication: URL normalization, content fingerprint           │
│                          ↓                                              │
│  2. VALIDATION (code-based, fast)                                       │
│     ├── URL accessible? (async HEAD request)                            │
│     ├── Content fetchable? (not paywalled, not empty)                   │
│     ├── Schema valid? (matches InboxItem shape)                         │
│     └── Not duplicate? (check against existing dataset)                 │
│                          ↓                                              │
│  3. AI SCORING (model-based → Silver tier)                              │
│     ├── Eval material quality: 1-5                                      │
│     ├── Category assignment (from predefined taxonomy)                  │
│     ├── Difficulty estimate (simple fetch vs multi-source)              │
│     ├── Score < 3: auto-reject (review if high scores sparse)           │
│     └── Score >= 3: route to annotation queue                           │
│                          ↓                                              │
│  4. HUMAN REVIEW (LangSmith Annotation Queue → Gold tier)               │
│     ├── Review AI-scored candidates sorted by score                     │
│     ├── Actions: Approve / Reject / Edit note                           │
│     ├── Attach feedback for AI scorer calibration                       │
│     └── "Add to Dataset" for approved items                             │
│                          ↓                                              │
│  5. FORMAT FOR EVAL (Gold → eval input shape)                           │
│     ├── Pull approved from LangSmith dataset                            │
│     ├── Transform to InboxItem: {item_type, content, note}              │
│     ├── Group into eval sets by category/difficulty                     │
│     └── Output: LangSmith dataset + local JSON (version controlled)     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Topic Categories

See [topic-taxonomy.md](./topic-taxonomy.md) for the full taxonomy defining bounded search scope for exploration subagents.

---

## Phase 3: Monitoring & Alerts

### Dashboard Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Error rate | Failed expansions / total | > 5% |
| Avg latency | Time per expansion | > 60s |
| Token usage | Tokens per expansion | > 10k |
| Tool efficiency | Redundant tool calls | > 2 per run |
| Eval scores | Rolling accuracy/relevance | < 3.5/5 |

### Alert Configuration

1. **Expansion failures**: Alert when error_rate > 5% over 1 hour
2. **Quality degradation**: Alert when avg eval score drops below threshold
3. **Cost spike**: Alert when token usage > 2x baseline

---

## Trace-Driven Development

> "Organizations lacking robust trace observability have zero visibility into actual system logic governing agent behavior." — [LangChain](https://blog.langchain.com/in-software-the-code-documents-the-app-in-ai-the-traces-do/)

### Manual Trace Review (Non-Negotiable)

**Weekly ritual**: Read 5-10 full traces manually. Eval scores often mask the real story.

Questions to ask while reading traces:
- Did the agent's reasoning make sense?
- Were tool calls in a logical order?
- Did it stop searching too early or too late?
- What would I have done differently?
- Is this a pattern I've seen before?

### Trace Inspection Workflow

1. **Expand a URL** → trace captured in LangSmith
2. **Review trace** → understand agent's reasoning path
3. **Identify issues** → add to dataset with annotation
4. **Iterate prompt/tools** → re-run, compare traces
5. **Validate fix** → run eval suite

### Team Trace Review (Like Code Review)

When multiple people work on the agent:
- Share interesting/problematic traces in Slack/docs
- Discuss reasoning patterns as a team
- Build shared intuition for "good" agent behavior

---

## Open Questions

1. **Eval frequency**: Run evaluators on every expansion or sample? (Recommendation: code-based on all, model-based on sample or on-demand)
2. **pass@k runs**: How many runs for non-determinism testing? (Start with k=3)
3. **Grader calibration cadence**: How often to validate model graders against human judgment? (Monthly minimum)
4. **Dataset size target**: How many golden examples before trusting evals? (Start with 20-50, grow to 100+)
5. **Cost budget**: LLM-as-judge adds ~$0.01-0.05 per eval. What's acceptable per run?

---

## References

### Core Methodology
- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — Multi-grader approach, pass@k, research agent patterns
- [LangChain: Traces Document AI Apps](https://blog.langchain.com/in-software-the-code-documents-the-app-in-ai-the-traces-do/) — Trace-driven development paradigm

### LangSmith Implementation
- [LangSmith @traceable](https://reference.langchain.com/python/langsmith/observability/sdk/run_helpers/#langsmith.run_helpers.traceable)
- [LangSmith Evaluation Concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
- [LangSmith SDK v0.2 Evaluations](https://blog.langchain.com/easier-evaluations-with-langsmith-sdk-v0-2/)
- [LangSmith Annotation Queues](https://docs.langchain.com/langsmith/annotation-queues) — Human review workflow
- [LangSmith Dataset Schemas](https://blog.langchain.com/dataset-schemas/) — Schema validation for datasets
- [OpenEvals Library](https://github.com/langchain-ai/openevals)
- [LangSmith Dashboards](https://docs.langchain.com/langsmith/dashboards)
- [LangSmith Alerts](https://blog.langchain.com/langsmith-alerts/)

### Agent Frameworks
- [DeepAgents](https://github.com/langchain-ai/deepagents) — Agent harness with planning, subagents, HITL
- [LangGraph Human-in-the-Loop](https://blog.langchain.com/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt/) — interrupt() and Command patterns
- [HITL Patterns: Approve, Reject, Edit](https://medium.com/the-advanced-school-of-ai/human-in-the-loop-in-langgraph-approve-or-reject-pattern-fcf6ba0c5990)

### Dataset Building
- [Building Golden Datasets](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/) — Quality tiers, continuous growth
- [Path to Golden Dataset (Microsoft)](https://medium.com/data-science-at-microsoft/the-path-to-a-golden-dataset-or-how-to-evaluate-your-rag-045e23d1f13f) — Silver to gold promotion
- [Gentrace: Building Datasets](https://gentrace.ai/blog/how-to-build-datasets) — Start small, grow continuously
