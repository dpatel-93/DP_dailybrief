"""Entry point for the command-check workflow. Handles /brief, /weekly, /markets, /save, /research, /queue, /list."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot_commands import checkForCommands, sendReply
from src.vault import (
    getArticleByIndex,
    loadDigestArticles,
    createSaveNote,
    createResearchNote,
    pushNoteToVault,
    loadQueue,
    saveQueue,
)
from src.main import run, loadConfig, resolveCategoryFilter
from datetime import datetime
import re


def main():
    print("Checking for Telegram commands...")
    commands = checkForCommands()

    hasWork = any(commands[k] for k in commands)
    if not hasWork:
        print("No commands found. Nothing to do.")
        return

    config = loadConfig()

    # --- /brief or /update (with optional filter) ---
    if commands["brief"]:
        print(f"Found {len(commands['brief'])} brief command(s) — running digest!")
        # Check first brief command for a filter
        firstBrief = commands["brief"][0]
        filterArg = firstBrief.get("filter")

        if filterArg:
            categoryFilter = resolveCategoryFilter(config, filterArg)
            if categoryFilter:
                sendReply(f"Got it! Generating {filterArg} brief... \u23f3")
                try:
                    run(categoryFilter=categoryFilter)
                except Exception as e:
                    print(f"[ERROR] Filtered digest failed: {e}")
                    sendReply(f"Failed to generate {filterArg} brief: {e}")
            else:
                sendReply(
                    f"Unknown filter: '{filterArg}'\n\n"
                    "Available filters: azure, ai, security, markets, news, health\n"
                    "Or use /brief for the full digest."
                )
        else:
            sendReply("Got it! Generating your brief now... \u23f3")
            try:
                run()
            except Exception as e:
                print(f"[ERROR] Digest generation failed: {e}")
                sendReply(f"Failed to generate brief: {e}")

    # --- /weekly ---
    if commands["weekly"]:
        print("Found weekly command — generating weekly summary!")
        sendReply("Generating your weekly summary... \u23f3")
        try:
            run(mode="weekly")
        except Exception as e:
            print(f"[ERROR] Weekly summary failed: {e}")
            sendReply(f"Failed to generate weekly summary: {e}")

    # --- /markets ---
    if commands["markets"]:
        print("Found markets command — generating pre-market brief!")
        sendReply("Generating pre-market brief... \U0001f4c8")
        try:
            run(mode="markets")
        except Exception as e:
            print(f"[ERROR] Markets brief failed: {e}")
            sendReply(f"Failed to generate markets brief: {e}")

    # --- /sports ---
    if commands["sports"]:
        print("Found sports command — generating sports brief!")
        sendReply("Generating sports brief... ⚽")
        try:
            run(mode="sports")
        except Exception as e:
            print(f"[ERROR] Sports brief failed: {e}")
            sendReply(f"Failed to generate sports brief: {e}")

    # --- /list ---
    if commands["list"]:
        handleList()

    # --- /save ---
    for cmd in commands["save"]:
        if cmd["type"] == "all":
            handleSaveAll()
        else:
            handleSave(cmd["index"])

    # --- /research ---
    for cmd in commands["research"]:
        handleResearch(cmd["index"])

    # --- /queue ---
    for cmd in commands["queue"]:
        handleQueue(cmd["index"])


def handleList():
    """Send a list of articles from the last digest."""
    articles = loadDigestArticles()
    if not articles:
        sendReply("No recent digest found. Send /brief first to generate one.")
        return

    lines = ["\U0001f4cb *Last Digest Articles*\n"]
    currentCat = ""
    for a in articles:
        if a["category"] != currentCat:
            currentCat = a["category"]
            lines.append(f"\n*{currentCat}*")
        priority = "\u2b50 " if a.get("isPriority") else ""
        trending = " \U0001f525" if a.get("trendingTopic") else ""
        lines.append(f"  {a['index']}. {priority}{a['title']}{trending}")

    lines.append("\n\U0001f4be /save <number> — Save to Obsidian")
    lines.append("\U0001f50d /research <number> — Deep research + save")
    lines.append("\U0001f4cc /queue <number> — Read later")
    sendReply("\n".join(lines))


def handleSave(index: int):
    """Save a specific article to the Obsidian vault."""
    article = getArticleByIndex(index)
    if not article:
        sendReply(f"Article #{index} not found. Send /list to see available articles.")
        return

    sendReply(f"\U0001f4be Saving #{index}: {article['title']}...")

    note = createSaveNote(article)
    filename = _safeFilename(article["title"]) + ".md"
    success = pushNoteToVault(
        filename,
        note,
        f"Save article: {article['title'][:60]}",
    )

    if success:
        sendReply(f"\u2705 Saved to Obsidian vault!\nDailyUpdates/{filename}")
    else:
        sendReply(f"\u274c Failed to save. Check GITHUB_TOKEN secret.")


def handleSaveAll():
    """Save all articles from the last digest."""
    articles = loadDigestArticles()
    if not articles:
        sendReply("No recent digest found. Send /brief first.")
        return

    sendReply(f"\U0001f4be Saving all {len(articles)} articles to Obsidian...")

    now = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# Daily Digest — {now}\n"]

    currentCat = ""
    for a in articles:
        if a["category"] != currentCat:
            currentCat = a["category"]
            lines.append(f"\n## {currentCat}\n")
        lines.append(f"### {a['index']}. {a['title']}")
        lines.append(f"- **Source**: {a['source']}")
        lines.append(f"- **Link**: [{a['title']}]({a['link']})")
        lines.append(f"- **Summary**: {a['summary'][:300]}")
        lines.append("")

    note = "\n".join(lines)
    filename = f"Digest-{now}.md"
    success = pushNoteToVault(filename, note, f"Save full digest for {now}")

    if success:
        sendReply(f"\u2705 Full digest saved!\nDailyUpdates/{filename}")
    else:
        sendReply(f"\u274c Failed to save. Check GITHUB_TOKEN secret.")


def handleResearch(index: int):
    """Deep research an article and save to vault."""
    article = getArticleByIndex(index)
    if not article:
        sendReply(f"Article #{index} not found. Send /list to see available articles.")
        return

    sendReply(f"\U0001f50d Researching #{index}: {article['title']}...\nThis may take 30 seconds.")

    note = createResearchNote(article)
    filename = "Research - " + _safeFilename(article["title"]) + ".md"
    success = pushNoteToVault(
        filename,
        note,
        f"Research article: {article['title'][:60]}",
    )

    if success:
        sendReply(f"\u2705 Research saved to Obsidian vault!\nDailyUpdates/{filename}")
    else:
        sendReply(f"\u274c Failed to save. Check GITHUB_TOKEN secret.")


def handleQueue(index: int):
    """Add an article to the read-later queue."""
    article = getArticleByIndex(index)
    if not article:
        sendReply(f"Article #{index} not found. Send /list to see available articles.")
        return

    queue = loadQueue()

    # Check for duplicates
    if any(q["link"] == article["link"] for q in queue):
        sendReply(f"\U0001f4cc Already in your queue: {article['title'][:50]}")
        return

    queue.append({
        "title": article["title"],
        "link": article["link"],
        "source": article["source"],
        "category": article["category"],
        "queuedAt": datetime.now().isoformat(),
    })
    saveQueue(queue)

    sendReply(
        f"\U0001f4cc Queued #{index}: {article['title'][:50]}\n"
        f"Queue size: {len(queue)} article(s)\n"
        f"Send /queue to see your full queue"
    )


def _safeFilename(title: str) -> str:
    """Convert a title to a safe filename."""
    safe = re.sub(r"[^\w\s-]", "", title)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:80]


if __name__ == "__main__":
    main()
