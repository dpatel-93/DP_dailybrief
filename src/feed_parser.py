"""RSS feed parser — fetches and ranks articles from configured feeds."""

import feedparser
import httpx
from datetime import datetime, timezone
from dateutil import parser as dateparser
from dataclasses import dataclass


@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    category: str


def fetchFeed(url: str, timeout: int = 15) -> feedparser.FeedParserDict:
    """Fetch RSS feed with a proper User-Agent to avoid 403s."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return feedparser.parse(resp.text)
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return feedparser.FeedParserDict(entries=[])


def parseEntry(entry, sourceName: str, category: str) -> Article | None:
    """Parse a single feed entry into an Article."""
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    if not title or not link:
        return None

    # Extract summary — prefer summary, fall back to description
    summary = entry.get("summary", entry.get("description", ""))
    # Strip HTML tags (rough but effective for RSS)
    import re
    summary = re.sub(r"<[^>]+>", "", summary).strip()
    summary = summary[:500]  # Cap length

    # Parse published date
    published = None
    for dateField in ["published", "updated", "created"]:
        raw = entry.get(dateField)
        if raw:
            try:
                published = dateparser.parse(raw)
                if published and published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                break
            except (ValueError, TypeError):
                continue

    if not published:
        published = datetime.now(timezone.utc)

    return Article(
        title=title,
        link=link,
        summary=summary,
        published=published,
        source=sourceName,
        category=category,
    )


def fetchCategory(categoryKey: str, categoryConfig: dict, maxAgeHours: int = 24) -> list[Article]:
    """Fetch all feeds for a category and return articles sorted by recency."""
    articles = []
    cutoff = datetime.now(timezone.utc).timestamp() - (maxAgeHours * 3600)

    for feed in categoryConfig["feeds"]:
        print(f"  Fetching {feed['name']}...")
        parsed = fetchFeed(feed["url"])

        for entry in parsed.entries:
            article = parseEntry(entry, feed["name"], categoryKey)
            if article and article.published.timestamp() > cutoff:
                articles.append(article)

    # Sort by published date (newest first), deduplicate by title
    articles.sort(key=lambda a: a.published, reverse=True)
    seen = set()
    unique = []
    for a in articles:
        normalizedTitle = a.title.lower().strip()
        if normalizedTitle not in seen:
            seen.add(normalizedTitle)
            unique.append(a)

    return unique


def fetchAllFeeds(config: dict) -> dict[str, list[Article]]:
    """Fetch articles for all categories. Returns {category_key: [Article, ...]}."""
    maxAge = config.get("settings", {}).get("max_age_hours", 24)
    limit = config.get("settings", {}).get("articles_per_category", 3)
    results = {}

    for key, catConfig in config.get("categories", {}).items():
        print(f"\n[{catConfig['name']}]")
        articles = fetchCategory(key, catConfig, maxAge)
        results[key] = articles[:limit]
        print(f"  Got {len(articles)} articles, keeping top {len(results[key])}")

    return results
