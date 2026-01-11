# Daily Digest - Design Guidance

## Core Concept

You seed interesting finds. Agent expands them, finds connections, builds understanding over time.

```
INBOX → EXPAND → DIGEST → ARCHIVE
```

## Principles

### Signal, Not Instructions
Notes capture **why you found something interesting** - not instructions for the agent. Agent uses your signal to understand perspective, then determines its own research direction.

### Agent Autonomy
Agent decides depth, searches, connections, and topics. You provide sparks; agent surfaces things you wouldn't find yourself.

### Accumulating Memory
Archive by topic. New runs reference prior research. Build on existing understanding.

### Fetch Once, Keep Forever
Cache all fetched content. Links rot, pages change, tweets disappear. Once fetched, always available.

## Quality Bar

### Digest Output
- Specific insights, not generic summaries
- Connections that aren't obvious from titles alone
- Open threads that are actionable research questions
- Worth the compute spent

### Agent Efficiency
- Primary source first, evaluate before supplementary searches
- Minimize redundant tool calls
- Output early, don't use all turns

### Research Depth
- Find things user wouldn't find themselves
- Practitioner insights over academic abstracts
- Implementations over announcements

## Open Questions (Discover Through Iteration)

- How deep for different item types?
- What makes a "related" item worth including?
- How much prior context to include?
- When are topics too granular vs too broad?
- Cache TTL for re-fetching updated content?

## Constraints

- Respect rate limits (GitHub 5k/hr, don't hammer sites)
- SSRF protection on URL fetching
- Batch processing (no real-time)
