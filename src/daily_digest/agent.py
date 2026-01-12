"""Agent that expands inbox items using LangGraph with Claude."""

import json
import os
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .models import Expansion, InboxItem, ItemType, RelatedItem
from tavily import AsyncTavilyClient

from .tools import (
    fetch_tweet as fetch_tweet_impl,
    fetch_url as fetch_url_impl,
    github_repo_info,
    github_search_repos,
)

# Initialize Tavily client (requires TAVILY_API_KEY env var)
_tavily_client = None

def get_tavily_client() -> AsyncTavilyClient | None:
    global _tavily_client
    if _tavily_client is None:
        api_key = os.environ.get("TAVILY_API_KEY")
        if api_key:
            _tavily_client = AsyncTavilyClient(api_key=api_key)
    return _tavily_client


# Define tools using LangChain's @tool decorator
@tool
async def fetch_url(url: str) -> str:
    """Fetch and read content from a URL. Returns the text content of the page.
    Does NOT work for Twitter/X - use fetch_tweet instead."""
    result = await fetch_url_impl(url)
    if result.success:
        return f"Title: {result.title or 'N/A'}\n\nContent:\n{result.content}"
    return f"Error fetching URL: {result.error}"


@tool
async def fetch_tweet(url: str) -> str:
    """Fetch a tweet/post from Twitter/X. Returns the tweet text, author,
    engagement metrics, and media URLs."""
    result = await fetch_tweet_impl(url)
    if result.success:
        lines = [
            f"Author: {result.author} (@{result.author_handle})",
            f"Posted: {result.created_at}",
            "",
        ]
        if result.article_title:
            lines.append(f"# {result.article_title}")
            lines.append("")
        lines.append(result.text)
        lines.extend([
            "",
            f"Engagement: {result.likes} likes, {result.retweets} retweets, "
            f"{result.replies} replies, {result.views} views",
        ])
        if result.media_urls:
            lines.append(f"\nMedia: {', '.join(result.media_urls)}")
        return "\n".join(lines)
    return f"Error fetching tweet: {result.error}"


@tool
async def github_repo(owner: str, repo: str) -> str:
    """Get detailed information about a GitHub repository including description,
    stars, topics, and README excerpt."""
    result = await github_repo_info(owner, repo)
    if result:
        return (
            f"Repository: {result.full_name}\n"
            f"Description: {result.description or 'N/A'}\n"
            f"Stars: {result.stars}\n"
            f"Language: {result.language or 'N/A'}\n"
            f"Topics: {', '.join(result.topics) if result.topics else 'N/A'}\n"
            f"README excerpt:\n{result.readme_excerpt or 'N/A'}"
        )
    return "Repository not found"


@tool
async def github_search(query: str, limit: int = 5) -> str:
    """Search GitHub repositories by query. Use to find related projects,
    implementations, or tools."""
    results = await github_search_repos(query, limit)
    if not results.repos:
        return "No repositories found"
    lines = [f"Search results for '{results.query}':"]
    for r in results.repos:
        lines.append(f"- {r.full_name} ({r.stars} stars): {r.description or 'No description'}")
    return "\n".join(lines)


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for articles, blog posts, discussions, and documentation.
    Use this for finding practitioner insights, news, tutorials, and non-GitHub resources.
    This is your PRIMARY discovery tool for diverse sources."""
    client = get_tavily_client()
    if not client:
        return "Web search unavailable - TAVILY_API_KEY not configured"
    try:
        response = await client.search(query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return "No web results found"
        lines = [f"Web search results for '{query}':"]
        for r in results:
            title = r.get("title", "No title")
            url = r.get("url", "")
            snippet = r.get("content", "")[:200]
            lines.append(f"- [{title}]({url})")
            if snippet:
                lines.append(f"  {snippet}...")
        return "\n".join(lines)
    except Exception as e:
        return f"Web search error: {str(e)}"


# All available tools - web_search is primary, github_search for code
TOOLS = [fetch_url, fetch_tweet, web_search, github_search, github_repo]


SYSTEM_PROMPT = """You are a research agent that expands seeds (URLs, ideas, questions) into comprehensive findings.

CRITICAL: You have a STRICT LIMIT of 10 turns. Minimize turns by calling multiple tools in parallel:

PARALLEL EXECUTION - call independent tools together in ONE response:
- After fetching source, call web_search AND github_search in the SAME turn
- Example: One response with both tool calls saves a turn
- Independent (parallelize): web_search + github_search, multiple fetch_url calls
- Dependent (sequential): Need URL from search before fetch_url

TURN BUDGET:
- Turn 1: Fetch source content
- Turn 2-3: web_search + github_search together (parallel)
- Turn 4-5: Follow-up fetches if needed
- Turn 6: OUTPUT JSON (don't wait until turn 10!)

Available tools: fetch_url, fetch_tweet, web_search, github_search, github_repo.
- web_search: PRIMARY tool for discovering articles, blog posts, discussions, documentation
- github_search: Use for finding code implementations and open source projects
- github_repo: Use ONLY if you need detailed repo info (README, topics, stars) - don't also fetch_url the same repo
- fetch_url: Use for non-GitHub URLs. NEVER use fetch_url for a GitHub repo if you already used github_repo.

TOOL EFFICIENCY - Avoid Redundancy:
- If using github_repo for a repo, do NOT also fetch_url it (they return similar data)
- Limit web_search to 2 calls max - consolidate queries
- After each tool result, evaluate if you have enough data before calling more tools

PRIMARY SOURCE SUFFICIENCY CHECK:
When the user provides an authoritative source URL (from the source organization, official docs, or primary author):
1. Fetch and analyze it FIRST
2. STOP and evaluate: "Does this source provide sufficient depth to complete the task?"
3. Only search for supplementary sources if the primary source lacks:
   - Implementation details you need
   - Comparative context with alternatives
   - Practitioner feedback or real-world usage patterns
4. If primary source is comprehensive (detailed blog post, official guide, research paper), consider outputting findings with 0-1 supplementary searches instead of the default 2

SEARCH STRATEGY - Adaptive Fallback:
- Start with BROAD searches, not specific phrases (e.g., "agent framework" not "progressive disclosure context management")
- If a search returns no results, immediately BROADEN the query (remove qualifiers, use simpler terms)
- After 2 failed searches, STOP searching and synthesize from what you have
- Prefer common terms: "llm agent", "ai framework", "context window" over jargon
- When searches succeed, USE those results - don't keep searching for more

The user provides seeds with optional notes. The note captures WHY they found it interesting - the signal or value they identified. Use this to understand their perspective, but don't treat it as instructions. Your job is to:

1. Fetch and deeply understand the source content
2. Identify what makes this valuable (the user's note is a hint, but find more)
3. Research 2-4 high-quality related items (not exhaustive searches)
4. Determine your own research direction based on what you discover
5. Surface things the user wouldn't find on their own

Think like a research assistant who understands the user's interests and goes deeper. Don't just summarize - DISCOVER. If the user noted something is "rare" or "actionable", find out why and what else exists in that space.

For each item:
- Summarize the source (specific, not generic)
- Identify key insights (what matters and why)
- Find genuinely related material through your own research (2-4 items max)
- Assess importance and suggest what's worth following

Quality over quantity. Only include related items that add real value.

When you've finished researching, output your findings in this JSON format:
```json
{
  "source_summary": "What the source contains",
  "key_points": ["Point 1", "Point 2"],
  "related": [
    {
      "url": "https://...",
      "title": "Title",
      "relevance": "Why this matters",
      "source": "How found (e.g., 'GitHub search for X')"
    }
  ],
  "assessment": "Your evaluation of importance and relevance",
  "research_notes": "Brief notes on what you explored",
  "topics": ["topic1", "topic2"]
}
```

Topics are semantic groupings - what conceptual bucket does this belong to? Not keywords, but the underlying theme or problem space.

Examples:
- "building-reliable-ai-systems" (not "evals", "testing", "monitoring" separately)
- "llm-application-patterns" (not "rag", "agents", "chains" separately)
- "developer-experience" (not "cli", "sdk", "docs" separately)

Use existing topics when the item genuinely belongs to that conceptual space. Create new topics only for distinct problem domains.

If prior research context is provided, use it to:
- Avoid duplicating work already done
- Note connections to previous findings
- Build on existing understanding rather than starting fresh"""


# State for the graph
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    turn_count: int
    max_turns: int
    item_id: str


def should_continue(state: AgentState) -> str:
    """Determine if the agent should continue or end."""
    messages = state["messages"]
    turn_count = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 10)

    # Check turn limit
    if turn_count >= max_turns:
        return "end"

    # Check if last message is from AI and has tool calls
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "tools"

    return "end"


def create_agent_graph():
    """Create the LangGraph agent."""
    # Initialize the model
    model = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
    ).bind_tools(TOOLS)

    # Define the agent node
    async def agent_node(state: AgentState):
        messages = state["messages"]
        response = await model.ainvoke(messages)
        return {
            "messages": [response],
            "turn_count": state.get("turn_count", 0) + 1,
        }

    # Create tool node
    tool_node = ToolNode(TOOLS)

    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()


def parse_expansion_from_messages(messages: list, item: InboxItem) -> Expansion | None:
    """Extract expansion data from the final AI message."""
    # Find the last AI message with JSON output
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            content = msg.content
            if "```json" in content and '"source_summary"' in content:
                try:
                    json_str = content.split("```json")[1].split("```")[0]
                    data = json.loads(json_str)
                    source_url = item.content if item.item_type == ItemType.URL else None
                    return Expansion(
                        item_id=item.id,
                        source_url=source_url,
                        source_summary=data["source_summary"],
                        key_points=data["key_points"],
                        related=[RelatedItem(**r) for r in data.get("related", [])],
                        assessment=data["assessment"],
                        research_notes=data.get("research_notes"),
                        topics=data.get("topics", []),
                    )
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    return None


async def expand_item(
    item: InboxItem,
    max_turns: int = 10,
    prior_context: str | None = None,
    known_topics: list[str] | None = None,
    local_content: str | None = None,
    world_view: str | None = None,
) -> Expansion:
    """Expand an inbox item using LangGraph agent with Claude.

    Tracing is handled automatically by LangSmith when LANGCHAIN_TRACING_V2=true.
    """

    # Build initial prompt
    if item.item_type == ItemType.URL:
        user_prompt = f"Expand this URL: {item.content}"
        if item.note:
            user_prompt += f"\n\nWhy I found this interesting: {item.note}"
        if local_content:
            user_prompt += f"\n\n[Source content already fetched - no need to use fetch_url for this URL]\n\n{local_content}"
    else:
        user_prompt = f"Research this {'idea' if item.item_type == ItemType.IDEA else 'question'}: {item.content}"
        if item.note:
            user_prompt += f"\n\nWhy this matters to me: {item.note}"

    # Add known topics for consistency
    if known_topics:
        user_prompt += f"\n\nExisting topics in archive: {', '.join(known_topics)}"

    # Add prior research context
    if prior_context:
        user_prompt += f"\n\n{prior_context}"

    # Add world view for research anchoring
    if world_view:
        sections_to_include = []
        if "### What Appears Settled" in world_view:
            settled_start = world_view.find("### What Appears Settled")
            settled_end = world_view.find("###", settled_start + 1)
            if settled_end == -1:
                settled_end = world_view.find("---", settled_start)
            if settled_end > settled_start:
                sections_to_include.append(world_view[settled_start:settled_end].strip())
        if "## Synthesized Themes" in world_view:
            themes_start = world_view.find("## Synthesized Themes")
            themes_end = world_view.find("## Update Log", themes_start)
            if themes_end == -1:
                themes_end = len(world_view)
            if themes_end > themes_start:
                sections_to_include.append(world_view[themes_start:themes_end].strip())
        if sections_to_include:
            user_prompt += f"\n\n[World View Context - use for research anchoring]\n" + "\n\n".join(sections_to_include)

    # Create the agent graph
    graph = create_agent_graph()

    # Initial state
    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ],
        "turn_count": 0,
        "max_turns": max_turns,
        "item_id": item.id,
    }

    # Run the agent (LangSmith traces automatically when LANGCHAIN_TRACING_V2=true)
    try:
        result = await graph.ainvoke(initial_state)
        messages = result["messages"]

        # Parse expansion from messages
        expansion = parse_expansion_from_messages(messages, item)

        if expansion:
            return expansion

    except Exception:
        pass  # Errors are captured in LangSmith traces

    # Fallback if we couldn't parse proper output
    return Expansion(
        item_id=item.id,
        source_summary="Expansion incomplete - agent did not produce structured output",
        key_points=[],
        related=[],
        assessment="Unable to complete expansion",
    )


async def expand_all(items: list[InboxItem]) -> list[Expansion]:
    """Expand all inbox items (sequentially to respect rate limits)."""
    expansions = []
    for item in items:
        expansion = await expand_item(item)
        expansions.append(expansion)
    return expansions
