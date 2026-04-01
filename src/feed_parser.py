"""RSS feed parser — fetches, deduplicates, tags priority, and detects trends."""

import re
import feedparser
import httpx
from datetime import datetime, timezone
from dateutil import parser as dateparser
from dataclasses import dataclass, field
from difflib import SequenceMatcher


@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    category: str
    isPriority: bool = False
    priorityMatches: list[str] = field(default_factory=list)
    trendingTopic: str = ""


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

    summary = entry.get("summary", entry.get("description", ""))
    summary = re.sub(r"<[^>]+>", "", summary).strip()
    summary = summary[:500]

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


def tagPriority(articles: list[Article], keywords: list[str]) -> list[Article]:
    """Tag articles that match priority keywords."""
    if not keywords:
        return articles

    patterns = [(kw, re.compile(re.escape(kw), re.IGNORECASE)) for kw in keywords]

    for article in articles:
        searchText = f"{article.title} {article.summary}"
        for kw, pattern in patterns:
            if pattern.search(searchText):
                article.isPriority = True
                article.priorityMatches.append(kw)

    return articles


def detectTrending(allArticles: list[Article], threshold: int = 3) -> list[Article]:
    """Detect trending topics — when 3+ articles from different sources cover the same topic."""
    if len(allArticles) < threshold:
        return allArticles

    # Group similar titles using fuzzy matching
    clusters = []
    used = set()

    for i, a in enumerate(allArticles):
        if i in used:
            continue
        cluster = [i]
        sources = {a.source}

        for j, b in enumerate(allArticles):
            if j <= i or j in used:
                continue
            # Compare title similarity
            ratio = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
            if ratio > 0.5 and b.source not in sources:
                cluster.append(j)
                sources.add(b.source)
                used.add(j)

        if len(sources) >= threshold:
            # Mark all articles in this cluster as trending
            topicLabel = allArticles[cluster[0]].title[:60]
            for idx in cluster:
                allArticles[idx].trendingTopic = topicLabel
            used.update(cluster)

    return allArticles


def deduplicateAcrossCategories(articlesByCategory: dict[str, list[Article]]) -> dict[str, list[Article]]:
    """Remove duplicate articles across categories. Keep the article in its first-appearing category."""
    seenTitles = {}  # normalized title -> category key

    for key, articles in articlesByCategory.items():
        deduped = []
        for a in articles:
            normalized = a.title.lower().strip()
            if normalized not in seenTitles:
                seenTitles[normalized] = key
                deduped.append(a)
            else:
                print(f"  [DEDUP] Skipping '{a.title[:50]}...' (already in {seenTitles[normalized]})")
        articlesByCategory[key] = deduped

    return articlesByCategory


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

    # Sort by published date (newest first), deduplicate by title within category
    articles.sort(key=lambda a: a.published, reverse=True)
    seen = set()
    unique = []
    for a in articles:
        normalizedTitle = a.title.lower().strip()
        if normalizedTitle not in seen:
            seen.add(normalizedTitle)
            unique.append(a)

    return unique


def fetchAllFeeds(config: dict, categoryFilter: list[str] = None) -> dict[str, list[Article]]:
    """Fetch articles for all (or filtered) categories.

    Args:
        config: Full config dict
        categoryFilter: Optional list of category keys to fetch. If None, fetches all.

    Returns {category_key: [Article, ...]}
    """
    maxAge = config.get("settings", {}).get("max_age_hours", 24)
    limit = config.get("settings", {}).get("articles_per_category", 3)
    priorityKeywords = config.get("settings", {}).get("priority_keywords", [])
    results = {}

    categories = config.get("categories", {})

    for key, catConfig in categories.items():
        if categoryFilter and key not in categoryFilter:
            continue

        print(f"\n[{catConfig['name']}]")
        articles = fetchCategory(key, catConfig, maxAge)

        # Tag priority articles
        if priorityKeywords:
            articles = tagPriority(articles, priorityKeywords)

        results[key] = articles[:limit]
        priorityCount = sum(1 for a in results[key] if a.isPriority)
        suffix = f" ({priorityCount} priority)" if priorityCount else ""
        print(f"  Got {len(articles)} articles, keeping top {len(results[key])}{suffix}")

    # Cross-category dedup
    results = deduplicateAcrossCategories(results)

    # Detect trending topics across all articles
    allArticles = [a for arts in results.values() for a in arts]
    detectTrending(allArticles)

    trendingCount = sum(1 for a in allArticles if a.trendingTopic)
    if trendingCount:
        print(f"\n  [TRENDING] {trendingCount} articles are part of trending topics")

    return results
