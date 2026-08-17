"""Obsidian vault integration — saves and researches articles to the vault GitHub repo."""

import os
import json
import httpx
from datetime import datetime
from groq import Groq

VAULT_REPO = "dpatel-93/DP_Obsidian_Vault"
VAULT_FOLDER = "DailyUpdates"  # Notes go to DailyUpdates/ folder in the vault
DIGEST_FILE = "data/last_digest.json"
QUEUE_FILE = "data/queue.json"
LATEST_BRIEF_FILE = "output/latest-brief.json"


# --- Digest Storage ---

def loadQueue() -> list[dict]:
    """Load the read-later queue."""
    queuePath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        QUEUE_FILE,
    )
    try:
        with open(queuePath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def saveQueue(queue: list[dict]):
    """Save the read-later queue."""
    queuePath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        QUEUE_FILE,
    )
    os.makedirs(os.path.dirname(queuePath), exist_ok=True)
    with open(queuePath, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)


def saveLatestBrief(digest: str, mode: str, articleCount: int):
    """Persist the finished brief text to a file the workflow commits back to
    this repo, so something outside Telegram (Alfred's HUD) can read the
    actual brief content via the GitHub contents API instead of just knowing
    whether the run succeeded."""
    briefPath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        LATEST_BRIEF_FILE,
    )
    os.makedirs(os.path.dirname(briefPath), exist_ok=True)
    with open(briefPath, "w", encoding="utf-8") as f:
        json.dump({
            "date": datetime.now().isoformat(),
            "mode": mode,
            "articleCount": articleCount,
            "digest": digest,
        }, f, indent=2)


def saveDigestArticles(articlesByCategory: dict, categoryConfigs: dict):
    """Save the current digest articles so /save and /research can reference them by number."""
    flat = []
    globalIdx = 1
    for key, articles in articlesByCategory.items():
        catName = categoryConfigs.get(key, {}).get("name", key)
        for a in articles:
            entry = {
                "index": globalIdx,
                "title": a.title,
                "link": a.link,
                "summary": a.summary,
                "source": a.source,
                "category": catName,
                "published": a.published.isoformat(),
            }
            if hasattr(a, "isPriority") and a.isPriority:
                entry["isPriority"] = True
                entry["priorityMatches"] = a.priorityMatches
            if hasattr(a, "trendingTopic") and a.trendingTopic:
                entry["trendingTopic"] = a.trendingTopic
            flat.append(entry)
            globalIdx += 1

    digestPath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        DIGEST_FILE,
    )
    os.makedirs(os.path.dirname(digestPath), exist_ok=True)
    with open(digestPath, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.now().isoformat(), "articles": flat}, f, indent=2)

    print(f"  Saved {len(flat)} articles to {DIGEST_FILE}")
    return flat


def loadDigestArticles() -> list[dict]:
    """Load the last digest's articles."""
    digestPath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        DIGEST_FILE,
    )
    try:
        with open(digestPath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("articles", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def getArticleByIndex(index: int) -> dict | None:
    """Get a specific article by its digest index number."""
    articles = loadDigestArticles()
    for a in articles:
        if a["index"] == index:
            return a
    return None


# --- Note Creation ---

def createSaveNote(article: dict) -> str:
    """Create a simple bookmark note for an article."""
    now = datetime.now().strftime("%Y-%m-%d")
    return f"""# {article['title']}
> Saved from DailyUpdates on {now}

## Summary
{article['summary'][:500]}

## Details
- **Source**: {article['source']}
- **Category**: {article['category']}
- **Published**: {article['published'][:10]}
- **Link**: [{article['title']}]({article['link']})

## My Notes
*(add your notes here)*
"""


def createResearchNote(article: dict) -> str:
    """Fetch the full article and create a deep research note using AI."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        return createSaveNote(article)  # Fallback to simple save

    # Try to fetch the full article content
    fullContent = _fetchArticleContent(article["link"])

    client = Groq(api_key=apiKey)
    prompt = f"""Research this article and create a comprehensive note:

Title: {article['title']}
Source: {article['source']}
Category: {article['category']}
Link: {article['link']}
Summary: {article['summary']}

{"Full article content:" + chr(10) + fullContent[:3000] if fullContent else "Full content not available, work from the summary."}

Create a research note with these sections:
1. **Key Takeaways** (3-5 bullet points)
2. **Why This Matters** (1-2 paragraphs, specifically for a Cloud Infrastructure Engineer managing Azure)
3. **Action Items** (what should I do or look into based on this?)
4. **Related Topics** (what other areas does this connect to?)

Be specific and actionable. No fluff."""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are a research assistant for a Cloud Infrastructure Engineer. Write concise, actionable research notes."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    researchContent = response.choices[0].message.content
    now = datetime.now().strftime("%Y-%m-%d")

    return f"""# {article['title']}
> Researched from DailyUpdates on {now}

## Source
- **Feed**: {article['source']}
- **Category**: {article['category']}
- **Published**: {article['published'][:10]}
- **Link**: [{article['title']}]({article['link']})

{researchContent}

## My Notes
*(add your notes here)*
"""


def _fetchArticleContent(url: str) -> str:
    """Try to fetch the full text content of an article."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        # Strip HTML tags (rough extraction)
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception:
        return ""


# --- GitHub Push ---

def pushNoteToVault(filename: str, content: str, commitMsg: str) -> bool:
    """Push a markdown note to the Obsidian vault GitHub repo."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("  [WARN] No GITHUB_TOKEN — cannot push to vault repo")
        return False

    path = f"{VAULT_FOLDER}/{filename}"
    url = f"https://api.github.com/repos/{VAULT_REPO}/contents/{path}"

    # Check if file already exists (need SHA to update)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    sha = None
    try:
        resp = httpx.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            sha = resp.json().get("sha")
    except Exception:
        pass

    import base64
    payload = {
        "message": commitMsg,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": "master",
    }
    if sha:
        payload["sha"] = sha

    try:
        resp = httpx.put(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in [200, 201]:
            print(f"  Pushed note to vault: {path}")
            return True
        else:
            print(f"  [ERROR] Failed to push: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  [ERROR] Push failed: {e}")
        return False
