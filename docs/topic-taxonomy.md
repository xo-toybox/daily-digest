# Topic Taxonomy for Eval Dataset

> Defines bounded search scope for seed input collection. Categories guide exploration subagents.

## Overview

Three-layer structure reflecting different perspectives on AI agent development:

1. **Engineering** — How to build agents (context, architecture, learning, eval)
2. **Product** — How humans interact with agents (UX, trust, adoption)
3. **Research/Theory** — Foundational questions and open problems

---

## Engineering Layer

### Context Engineering

The core challenge in production agents ([Lance Martin](https://x.com/RLanceMartin/status/2009683038272401719)).

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `context-offloading` | Filesystem for persistent context | Summarization tradeoffs, tool result storage |
| `context-caching` | Prompt caching for cost/latency | Cache hit rate optimization, prefix reuse |
| `context-isolation` | Sub-agents with separate windows | Ralph loops, parallel execution, map-reduce |
| `progressive-disclosure` | Just-in-time information loading | MCP management, skill frontmatter, tool indexing |
| `context-compression` | Reducing context while preserving signal | Trajectory reduction, working memory limits |
| `recursive-context-management` | Models learning to manage own context | [RLM](https://arxiv.org/html/2512.24601v1), 10M+ token processing |

### Agent Architecture

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `computer-use` | Give agents a computer | Filesystem, shell, OS primitives, Claude Code pattern |
| `action-space-design` | Multi-layer action hierarchy | Atomic tools → shell → code execution, CodeAct |
| `sub-agent-coordination` | Multi-agent collaboration | [Swarms](https://www.swarmtools.ai/), conflict resolution, shared state, file locking |
| `human-in-the-loop` | Verification and approval | Stop hooks, interrupt patterns, approval workflows |
| `sleep-time-compute` | Background processing | [Letta](https://www.letta.com/blog/sleep-time-compute), offline reflection, pre-computation |

### Continual Learning

Your key focus area — self-reinforcing feedback loops for autonomy.

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `metacognition` | Self-assessment and calibration | Confidence estimation, knowing unknowns |
| `context-evolution` | Learning from trajectories | Reflect → update prompts/memories/skills |
| `procedural-memory` | Skill libraries and reuse | [ReMe](https://arxiv.org/html/2512.10696v1), [Memp](https://arxiv.org/html/2508.06433v2), Voyager skills |
| `learned-context-management` | Models absorbing scaffolding | Bitter Lesson applied to agents |
| `feedback-loops` | Self-correction mechanisms | Outcome-based learning, trajectory scoring |

### Eval & Observability

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `agent-evaluation` | Measuring agent quality | Benchmarks, pass@k, trajectory scoring |
| `trace-driven-development` | Traces as documentation | Debug via reasoning chains, not code |
| `benchmark-design` | Creating useful evals | Avoiding saturation, capability elicitation |
| `long-running-observability` | Monitoring extended tasks | Open problem — no standards yet |

### Safety & Security

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `sandboxing` | Isolated execution | gVisor, Firecracker, Docker rootless |
| `guardrails` | Runtime policy enforcement | [Superagent](https://www.helpnetsecurity.com/2025/12/29/superagent-framework-guardrails-agentic-ai/), content filtering |
| `tool-access-control` | Least privilege for agents | Capability scoping, short-lived credentials |
| `multi-agent-security` | Swarm-specific risks | Cascade failures, memory poisoning |

---

## Product Layer

### Agent Experience (AX)

New design discipline — "How will an agent understand, act, and collaborate here?"

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `human-agent-handoff` | Control transitions | Workflow state preservation, frictionless switching |
| `transparency-patterns` | Making agent reasoning visible | Thought logs, action explanations, [Microsoft AX](https://microsoft.design/articles/ux-design-for-agents/) |
| `autonomy-calibration` | User control over proactiveness | Sliders, toggles, permission settings |
| `persistent-dashboards` | Cross-session state visibility | Async status, pending actions, objectives |
| `conversational-interfaces` | Beyond chat | Voice, visual, multimodal flow |

### Trust & Adoption

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `progressive-autonomy` | Staged deployment | Shadow mode → limited → full |
| `error-recovery-ux` | Graceful degradation | Human escalation, rollback patterns |
| `personalization` | Memory-driven adaptation | Preference learning, cross-session continuity |
| `collaborative-patterns` | Agent as co-worker | ColBench-style interaction, clarification loops |

---

## Research/Theory Layer

Serendipitous areas — foundational questions and active debates.

### Cognitive Foundations

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `world-models` | Physics-aware reasoning | MLLM+WM integration, spatial simulation |
| `grounding-challenges` | Connecting symbols to reality | Multimodal feedback, tool grounding, environment |
| `theory-of-mind` | Modeling mental states | User intent, other-agent reasoning |
| `coherence-vs-grounding` | Can meaning emerge from coherence alone? | Active debate, [symbol ungrounding](https://pmc.ncbi.nlm.nih.gov/articles/PMC11529626/) |

### Alignment & Values

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `reward-hacking` | Specification gaming | [Chess agents cheating Stockfish](https://www.alignmentforum.org/posts/wwRgR3K8FKShjwwL5/), Goodhart's Law |
| `moral-alignment` | Value learning for agents | Intrinsic rewards, [ICLR 2025 paper](https://www.mircomusolesi.org/papers/iclr25_moral_alignment_llm_agents.pdf) |
| `mesa-optimization` | Learned optimizers | Inner alignment, emergent goals |
| `cot-faithfulness` | Do explanations reflect reasoning? | [Oxford research](https://aigi.ox.ac.uk/wp-content/uploads/2025/07/Cot_Is_Not_Explainability.pdf), monitorability |

### Interpretability

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `mechanistic-interpretability` | Circuit-level understanding | Activation patching, scaling challenges |
| `cot-monitorability` | Using CoT for safety oversight | Faithfulness as proxy for safety |
| `behavioral-interpretability` | What agents do vs. explain | Empirical behavior analysis |

### Economics & Society

| Topic | Description | Key Concepts |
|-------|-------------|--------------|
| `task-decomposition-economics` | Which tasks automate vs. augment? | [WORKBank](https://arxiv.org/abs/2506.06576), Human Agency Scale |
| `labor-market-effects` | Job transformation patterns | Skill demand shifts, 80% task exposure |
| `capability-elicitation` | Gap between capability and performance | Better scaffolding → better results |

---

## Usage Notes

### For Seed Input Collection

Each topic category defines:
- **Search constraints**: Keywords, domains to include/exclude
- **Target count**: 3-5 seeds per topic initially
- **Difficulty spread**: Mix of easy (single fetch) and hard (multi-source)

### Granularity Principle

Granularity varies by area maturity:
- **Deep** for active engineering areas (context engineering, continual learning)
- **Flat** for emerging areas (product, research/theory)

### Evolution

This taxonomy should evolve:
- Add topics as new patterns emerge
- Merge topics that prove redundant
- Split topics that become too broad
- Archive topics that become stale

---

## References

### Primary Sources
- [Lance Martin: Effective Agent Design](https://x.com/RLanceMartin/status/2009683038272401719) — Practitioner synthesis
- [Anthropic: Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Official guidance
- [Letta: Continual Learning in Token Space](https://www.letta.com/blog/continual-learning) — Memory architecture

### Research
- [RLM: Recursive Language Models](https://arxiv.org/html/2512.24601v1) — Learned context management
- [ReMe: Dynamic Procedural Memory](https://arxiv.org/html/2512.10696v1) — Skill distillation
- [Sleep-time Compute](https://www.letta.com/blog/sleep-time-compute) — Background processing

### Product/UX
- [Microsoft: UX Design for Agents](https://microsoft.design/articles/ux-design-for-agents/) — Design principles
- [UX Magazine: Agentic UX](https://uxmag.com/articles/secrets-of-agentic-ux-emerging-design-patterns-for-human-interaction-with-ai-agents) — Emerging patterns
