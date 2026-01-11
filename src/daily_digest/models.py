"""Data models for inbox items, expansions, and digests."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl


class ItemType(str, Enum):
    URL = "url"
    IDEA = "idea"
    QUESTION = "question"


class InboxItem(BaseModel):
    """A seed item to be expanded by the agent."""

    id: str = Field(description="Unique identifier (timestamp-based)")
    content: str = Field(description="URL or idea/question text")
    item_type: ItemType = Field(description="Type of item")
    note: str | None = Field(default=None, description="Why you found this interesting - the signal/value you identified")
    local_content: str | None = Field(default=None, description="Path to locally stored content for gated sources")
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_url(cls, url: str, note: str | None = None, local_content: str | None = None) -> "InboxItem":
        return cls(
            id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            content=url,
            item_type=ItemType.URL,
            note=note,
            local_content=local_content,
        )

    @classmethod
    def from_idea(cls, idea: str, note: str | None = None) -> "InboxItem":
        return cls(
            id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            content=idea,
            item_type=ItemType.IDEA,
            note=note,
        )


class RelatedItem(BaseModel):
    """A related resource discovered during expansion."""

    url: str
    title: str
    relevance: str = Field(description="Why this is relevant to the source")
    source: str = Field(description="How it was found (e.g., 'HN discussion', 'GitHub search')")


class Expansion(BaseModel):
    """Result of expanding an inbox item."""

    item_id: str
    source_url: str | None = Field(default=None, description="Original URL if applicable")
    source_summary: str = Field(description="What the source contains")
    key_points: list[str] = Field(description="Main takeaways")
    related: list[RelatedItem] = Field(default_factory=list)
    assessment: str = Field(description="Agent's evaluation of relevance/importance")
    research_notes: str | None = Field(default=None, description="Agent's working notes")
    topics: list[str] = Field(default_factory=list, description="Semantic groupings - conceptual buckets, not keywords (e.g., 'building-reliable-ai-systems')")
    expanded_at: datetime = Field(default_factory=datetime.now)


class DigestEntry(BaseModel):
    """Summary of one expansion for the digest."""

    item_id: str
    title: str
    one_liner: str
    key_finding: str
    worth_following: list[str] = Field(default_factory=list)


class Digest(BaseModel):
    """Daily digest summarizing expansions."""

    date: str
    entries: list[DigestEntry]
    cross_connections: list[str] = Field(
        default_factory=list, description="Connections between items"
    )
    open_threads: list[str] = Field(
        default_factory=list, description="Worth investigating further"
    )
