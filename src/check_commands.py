"""Entry point for the command-check workflow. Handles /brief, /save, /research, /list."""

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
)
from src.main import run
from datetime import datetime
import re


def main():
    print("Checking for Telegram commands...")
    commands = checkForCommands()

    hasWork = any(commands[k] for k in commands)
    if not hasWork:
        print("No commands found. Nothing to do.")
        return

    # --- /brief or /update ---
    if commands["brief"]:
        print(f"Found {len(commands['brief'])} brief command(s) — running digest!")
        sendReply("Got it! Generating your brief now... \u23f3")
        run()

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
        lines.append(f"  {a['index']}. {a['title']}")

    lines.append("\n\U0001f4be /save <number> — Save to Obsidian")
    lines.append("\U0001f50d /research <number> — Deep research + save")
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

    # Create a single combined note for the full digest
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


def _safeFilename(title: str) -> str:
    """Convert a title to a safe filename."""
    safe = re.sub(r"[^\w\s-]", "", title)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:80]


if __name__ == "__main__":
    main()
