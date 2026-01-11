# Ralph Loop 2: Seed Data Generation Pipeline

Read and update tracking at `.ralph/IMPROVEMENTS-seed-gen.md`.
Reference specs: `docs/observability-impl.md` (Step 4: Seed Input Collection), `docs/topic-taxonomy.md`.

## Objective

Implement and iterate the seed collection pipeline using DeepAgents until it reliably produces high-quality, diverse eval inputs across topic categories.

## Core Loop

1. Implement `daily-digest seeds collect` per spec
2. Run collection for 1-3 topic categories
3. Review with parallel subagents (below)
4. Adjust prompts/constraints based on findings
5. Repeat until exit criteria met

## Reviewer Subagents

**Collection Quality Reviewer:** Attacks the collected URLs.
- Relevance: What % are actually on-topic (not just keyword match)?
- Diversity: How many unique domains? Content types?
- Substance: Would these produce meaningful expansions?
- Gaps: What should have been found but wasn't?

**Agent Efficiency Reviewer:** Attacks the collection process.
- Searches per valid URL (target: <2)
- Redundant operations?
- Early stopping working?
- Subagent coordination clean?

**Reviewer calibration:** Surface 3-5 concrete prompt/constraint changes per review. "Found good URLs" is not useful. "Add domain diversity constraint, all 8 URLs from same blog" is useful. If >30% URLs are off-topic or <3 domains represented, that's a critical finding requiring prompt rework.

## Exit Criteria

Stop when:
1. 5+ quality URLs per category
2. >80% on-topic
3. No category dominated by <3 domains
4. <2 searches per valid URL
5. >70% pass validation
