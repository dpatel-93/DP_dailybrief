"""DailyUpdates — main orchestrator.

Pipeline: Fetch RSS → AI Summarize → TTS Audio → Deliver via Telegram
Supports: full brief, filtered brief, weekly summary, market brief
"""

import os
import sys
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feed_parser import fetchAllFeeds
from src.summarizer import summarizeDigest, summarizeWeekly, summarizeMarkets, makeSpokenVersion
from src.tts import generateAudio
from src.telegram import sendMessage, sendAudio
from src.vault import saveDigestArticles


def loadConfig(configPath: str = None) -> dict:
    """Load configuration from config.yaml."""
    if not configPath:
        configPath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml",
        )
    with open(configPath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolveCategoryFilter(config: dict, groupName: str = None) -> list[str] | None:
    """Resolve a category group name to a list of category keys.

    Args:
        config: Full config dict
        groupName: e.g., 'azure', 'markets', 'security'. None = all categories.

    Returns list of category keys, or None for all.
    """
    if not groupName:
        return None

    groups = config.get("settings", {}).get("category_groups", {})
    groupName = groupName.lower().strip()

    if groupName in groups:
        return groups[groupName]

    # Try matching a single category key directly
    if groupName in config.get("categories", {}):
        return [groupName]

    # Fuzzy match — check if group name is a prefix of any group
    for name, keys in groups.items():
        if name.startswith(groupName):
            return keys

    return None


def run(categoryFilter: list[str] = None, mode: str = "daily"):
    """Main pipeline: fetch → summarize → TTS → deliver.

    Args:
        categoryFilter: Optional list of category keys to include. None = all.
        mode: 'daily' (default), 'weekly', or 'markets'
    """
    print("=" * 60)
    print(f"DailyUpdates [{mode}] — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    config = loadConfig()
    settings = config.get("settings", {})
    categories = config.get("categories", {})

    # Override max_age for weekly mode
    if mode == "weekly":
        settings["max_age_hours"] = settings.get("weekly_max_age_hours", 168)
        config["settings"] = settings

    # For markets mode, auto-filter to market categories
    if mode == "markets" and not categoryFilter:
        categoryFilter = resolveCategoryFilter(config, "markets")

    # --- Step 1: Fetch RSS Feeds ---
    filterLabel = ""
    if categoryFilter:
        filterLabel = f" (filtered: {len(categoryFilter)} categories)"
    print(f"\n[Step 1/4] Fetching RSS feeds...{filterLabel}")
    articlesByCategory = fetchAllFeeds(config, categoryFilter=categoryFilter)

    totalArticles = sum(len(a) for a in articlesByCategory.values())
    if totalArticles == 0:
        print("\nNo articles found. Sending a 'quiet day' message.")
        sendMessage("No new updates found for this request. \U0001f60e")
        return

    # --- Save article index (for /save and /research commands) ---
    print("\n  Saving article index for /save and /research commands...")
    saveDigestArticles(articlesByCategory, categories)

    # --- Step 2: AI Summarization ---
    print(f"\n[Step 2/4] Generating AI summary ({mode} mode)...")
    model = settings.get("llm_model", "llama-3.3-70b-versatile")

    if mode == "weekly":
        digest = summarizeWeekly(articlesByCategory, categories, model=model)
    elif mode == "markets":
        digest = summarizeMarkets(articlesByCategory, categories, model=model)
    else:
        digest = summarizeDigest(articlesByCategory, categories, model=model)

    print(f"  Digest length: {len(digest)} chars")

    # --- Step 3: Text-to-Speech ---
    print("\n[Step 3/4] Generating audio...")
    voice = settings.get("tts_voice", "en-US-GuyNeural")
    spokenText = makeSpokenVersion(digest, categories)
    audioPath = generateAudio(spokenText, voice=voice)

    # --- Step 4: Deliver via Telegram ---
    print("\n[Step 4/4] Sending to Telegram...")

    modeLabels = {
        "daily": "Daily Brief",
        "weekly": "Weekly Summary",
        "markets": "Pre-Market Brief",
    }
    label = modeLabels.get(mode, "Brief")
    dateStr = datetime.now().strftime("%B %d, %Y")
    header = f"\U0001f4f0 *{label} — {dateStr}*\n"
    fullMessage = header + "\n" + digest
    result = sendMessage(fullMessage)
    if result.get("ok"):
        print("  Text message sent!")
    else:
        print(f"  [ERROR] Text send failed: {result}")

    # Send command instructions
    tips = (
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "\U0001f3a7 Audio version is below\n\n"
        "Commands:\n"
        "/list — See all articles by number\n"
        "/save <number> — Save article to Obsidian\n"
        "/research <number> — AI deep-dive + save\n"
        "/save all — Save full digest to Obsidian\n"
        "/brief — Full update\n"
        "/brief azure — Azure only\n"
        "/brief security — SecOps only\n"
        "/brief markets — Markets only\n"
        "/markets — Pre-market brief\n"
        "/weekly — Week in review\n"
        "/queue <number> — Read later"
    )
    sendMessage(tips, parseMode="Markdown")

    audioResult = sendAudio(audioPath, caption=f"\U0001f3a7 Listen to today's {label.lower()} ({datetime.now().strftime('%b %d')})")
    if audioResult.get("ok"):
        print("  Audio sent!")
    else:
        print(f"  [ERROR] Audio send failed: {audioResult}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    run()
