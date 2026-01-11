"""Tools for fetching web content and GitHub data."""

import hashlib
import ipaddress
import json
import os
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
from langsmith import traceable

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
USER_AGENT = "daily-digest/0.1 (research agent)"
FETCH_CACHE_DIR = Path("fetch_cache")

# SSRF Protection: Blocked schemes and port ranges
ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_PORTS = {22, 23, 25, 445, 3306, 5432, 6379, 27017}  # SSH, Telnet, SMTP, SMB, DB ports


def _is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to private/internal IP."""
    try:
        # Resolve hostname to IP
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        # Block private, loopback, link-local, and reserved ranges
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or str(ip).startswith("169.254.")  # Link-local
            or str(ip).startswith("0.")  # Current network
        )
    except (socket.gaierror, ValueError):
        # If we can't resolve, allow (might be valid external host)
        return False


def validate_url_security(url: str) -> tuple[bool, str | None]:
    """Validate URL for SSRF protection. Returns (is_safe, error_message)."""
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"Blocked scheme: {parsed.scheme}. Only http/https allowed."

        # Check for empty or suspicious hostname
        if not parsed.hostname:
            return False, "Invalid URL: no hostname"

        # Check port
        port = parsed.port
        if port and port in BLOCKED_PORTS:
            return False, f"Blocked port: {port}"

        # Check for private IPs (SSRF protection)
        if _is_private_ip(parsed.hostname):
            return False, f"Blocked: {parsed.hostname} resolves to private/internal IP"

        # Block obvious localhost variants
        hostname_lower = parsed.hostname.lower()
        if hostname_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False, "Blocked: localhost access not allowed"

        return True, None

    except Exception as e:
        return False, f"URL validation error: {str(e)}"


def _cache_key(url: str) -> str:
    """Generate cache filename from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _read_cache(url: str) -> dict | None:
    """Read cached content for URL."""
    cache_file = FETCH_CACHE_DIR / f"{_cache_key(url)}.json"
    if cache_file.exists():
        with cache_file.open() as f:
            return json.load(f)
    return None


def _write_cache(url: str, data: dict) -> None:
    """Write content to cache."""
    FETCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = FETCH_CACHE_DIR / f"{_cache_key(url)}.json"
    with cache_file.open("w") as f:
        json.dump({"url": url, **data}, f, indent=2)


class HTMLToText(HTMLParser):
    """Simple HTML to text converter."""

    def __init__(self):
        super().__init__()
        self.text = []
        self.skip_tags = {"script", "style", "nav", "footer", "header"}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.current_skip = max(0, self.current_skip - 1)
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.text.append("\n")

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self.text)


@dataclass
class FetchResult:
    """Result of fetching a URL."""

    url: str
    success: bool
    content: str | None = None
    title: str | None = None
    error: str | None = None
    content_type: str | None = None


@traceable(run_type="tool", tags=["fetch"])
async def fetch_url(
    url: str, timeout: float = 30.0, use_cache: bool = True, max_redirects: int = 5
) -> FetchResult:
    """Fetch URL content and convert HTML to readable text. Caches to filesystem."""
    # SSRF Protection: Validate URL before fetching
    is_safe, error_msg = validate_url_security(url)
    if not is_safe:
        return FetchResult(url=url, success=False, error=error_msg)

    # Check cache first
    if use_cache:
        cached = _read_cache(url)
        if cached and cached.get("type") == "webpage":
            return FetchResult(
                url=url,
                success=True,
                content=cached.get("content"),
                title=cached.get("title"),
                content_type=cached.get("content_type"),
            )

    # Disable auto-redirects; validate each redirect target for SSRF protection
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
        try:
            headers = {"User-Agent": USER_AGENT}
            current_url = url
            for _ in range(max_redirects):
                resp = await client.get(current_url, headers=headers)
                if resp.is_redirect:
                    redirect_url = str(resp.headers.get("location", ""))
                    if not redirect_url:
                        return FetchResult(url=url, success=False, error="Redirect with no location")
                    # Handle relative redirects
                    if redirect_url.startswith("/"):
                        parsed = urlparse(current_url)
                        redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                    # Validate redirect target for SSRF
                    is_safe, error_msg = validate_url_security(redirect_url)
                    if not is_safe:
                        return FetchResult(url=url, success=False, error=f"Blocked redirect: {error_msg}")
                    current_url = redirect_url
                    continue
                break
            else:
                return FetchResult(url=url, success=False, error="Too many redirects")
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            title = None
            content = None

            if "text/html" in content_type:
                html = resp.text
                # Extract title
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
                title = title_match.group(1).strip() if title_match else None

                parser = HTMLToText()
                parser.feed(html)
                content = parser.get_text()

                # Truncate if too long
                if len(content) > 50000:
                    content = content[:50000] + "\n[truncated]"

            elif "application/json" in content_type:
                content = json.dumps(resp.json(), indent=2)[:50000]
            else:
                # Plain text or other
                content = resp.text[:50000]

            result = FetchResult(
                url=url, success=True, content=content, title=title, content_type=content_type
            )

            # Cache the result
            _write_cache(url, {
                "type": "webpage",
                "content": result.content,
                "title": result.title,
                "content_type": result.content_type,
            })

            return result

        except httpx.HTTPStatusError as e:
            return FetchResult(url=url, success=False, error=f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            return FetchResult(url=url, success=False, error=str(e))


@dataclass
class GitHubRepo:
    """GitHub repository info."""

    full_name: str
    description: str | None
    stars: int
    language: str | None
    topics: list[str]
    readme_excerpt: str | None = None


@dataclass
class GitHubSearchResult:
    """GitHub search results."""

    query: str
    repos: list[GitHubRepo]


@traceable(run_type="tool", tags=["github"])
async def github_repo_info(owner: str, repo: str) -> GitHubRepo | None:
    """Get GitHub repository information."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}", headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

            # Try to get README
            readme_excerpt = None
            try:
                readme_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/readme",
                    headers={**headers, "Accept": "application/vnd.github.v3.raw"},
                )
                if readme_resp.status_code == 200:
                    readme_excerpt = readme_resp.text[:2000]
            except Exception:
                pass

            return GitHubRepo(
                full_name=data["full_name"],
                description=data.get("description"),
                stars=data["stargazers_count"],
                language=data.get("language"),
                topics=data.get("topics", []),
                readme_excerpt=readme_excerpt,
            )
        except Exception:
            return None


@traceable(run_type="tool", tags=["github"])
async def github_search_repos(query: str, limit: int = 5) -> GitHubSearchResult:
    """Search GitHub repositories."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "per_page": limit},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            repos = [
                GitHubRepo(
                    full_name=item["full_name"],
                    description=item.get("description"),
                    stars=item["stargazers_count"],
                    language=item.get("language"),
                    topics=item.get("topics", []),
                )
                for item in data.get("items", [])
            ]
            return GitHubSearchResult(query=query, repos=repos)
        except Exception:
            return GitHubSearchResult(query=query, repos=[])


def parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract owner/repo from GitHub URL."""
    parsed = urlparse(url)
    if "github.com" not in parsed.netloc:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def parse_twitter_url(url: str) -> tuple[str, str] | None:
    """Extract username and tweet ID from Twitter/X URL."""
    parsed = urlparse(url)
    if parsed.netloc not in ("twitter.com", "x.com", "www.twitter.com", "www.x.com"):
        return None
    # URL format: twitter.com/username/status/tweet_id
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 3 and parts[1] == "status":
        return parts[0], parts[2]
    return None


@dataclass
class TweetResult:
    """Result of fetching a tweet."""

    url: str
    success: bool
    author: str | None = None
    author_handle: str | None = None
    text: str | None = None  # Tweet text, or full article content for articles
    created_at: str | None = None
    likes: int | None = None
    retweets: int | None = None
    replies: int | None = None
    views: int | None = None
    media_urls: list[str] | None = None
    article_title: str | None = None  # Set if this is a Twitter article (long-form)
    error: str | None = None


def _extract_article_content(article: dict) -> str | None:
    """Extract full text content from Twitter article blocks."""
    content = article.get("content", {})
    blocks = content.get("blocks", [])
    if not blocks:
        return None

    lines = []
    for block in blocks:
        block_type = block.get("type", "")
        text = block.get("text", "").strip()

        if not text:
            continue

        if block_type.startswith("header-"):
            # Headers - add markdown formatting
            level = block_type.replace("header-", "")
            if level == "one":
                lines.append(f"\n# {text}\n")
            elif level == "two":
                lines.append(f"\n## {text}\n")
            elif level == "three":
                lines.append(f"\n### {text}\n")
            else:
                lines.append(f"\n**{text}**\n")
        elif block_type == "blockquote":
            lines.append(f"> {text}")
        elif block_type == "unordered-list-item":
            lines.append(f"- {text}")
        elif block_type == "ordered-list-item":
            lines.append(f"1. {text}")
        elif block_type == "code-block":
            lines.append(f"```\n{text}\n```")
        elif block_type == "atomic":
            # Skip media placeholders
            continue
        else:
            # unstyled or other - regular paragraph
            lines.append(text)

    return "\n\n".join(lines) if lines else None


@traceable(run_type="tool", tags=["fetch", "twitter"])
async def fetch_tweet(url: str, use_cache: bool = True) -> TweetResult:
    """Fetch tweet content via fxtwitter API. Caches to filesystem."""
    parsed = parse_twitter_url(url)
    if not parsed:
        return TweetResult(url=url, success=False, error="Invalid Twitter/X URL")

    # Check cache first
    if use_cache:
        cached = _read_cache(url)
        if cached and cached.get("type") == "tweet":
            return TweetResult(
                url=url,
                success=True,
                author=cached.get("author"),
                author_handle=cached.get("author_handle"),
                text=cached.get("text"),
                created_at=cached.get("created_at"),
                likes=cached.get("likes"),
                retweets=cached.get("retweets"),
                replies=cached.get("replies"),
                views=cached.get("views"),
                media_urls=cached.get("media_urls"),
                article_title=cached.get("article_title"),
            )

    username, tweet_id = parsed

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Use fxtwitter API - no auth required
            api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
            headers = {"User-Agent": USER_AGENT}

            resp = await client.get(api_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200:
                return TweetResult(
                    url=url,
                    success=False,
                    error=data.get("message", "Unknown error"),
                )

            tweet = data.get("tweet", {})
            author = tweet.get("author", {})

            # Extract media URLs if present
            media_urls = []
            if tweet.get("media") and tweet["media"].get("all"):
                for m in tweet["media"]["all"]:
                    if m.get("url"):
                        media_urls.append(m["url"])

            # Handle Twitter articles (long-form posts)
            article = tweet.get("article")
            article_title = None
            article_content = None
            if article:
                article_title = article.get("title")
                article_content = _extract_article_content(article)

            # Get text - use article content for articles, fall back to tweet text
            text = tweet.get("text") or ""
            if article_content:
                text = article_content

            result = TweetResult(
                url=url,
                success=True,
                author=author.get("name"),
                author_handle=author.get("screen_name"),
                text=text,
                created_at=tweet.get("created_at"),
                likes=tweet.get("likes"),
                retweets=tweet.get("retweets"),
                replies=tweet.get("replies"),
                views=tweet.get("views"),
                media_urls=media_urls if media_urls else None,
                article_title=article_title,
            )

            # Cache the result
            _write_cache(url, {
                "type": "tweet",
                "author": result.author,
                "author_handle": result.author_handle,
                "text": result.text,
                "created_at": result.created_at,
                "likes": result.likes,
                "retweets": result.retweets,
                "replies": result.replies,
                "views": result.views,
                "media_urls": result.media_urls,
                "article_title": result.article_title,
            })

            return result

        except httpx.HTTPStatusError as e:
            return TweetResult(url=url, success=False, error=f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            return TweetResult(url=url, success=False, error=str(e))
        except (KeyError, json.JSONDecodeError) as e:
            return TweetResult(url=url, success=False, error=f"Parse error: {e}")
