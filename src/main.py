"""DailyUpdates — main orchestrator.

Pipeline: Fetch RSS → AI Summarize → TTS Audio → Deliver via Telegram
Supports: full brief, filtered brief, weekly summary, market brief
"""

import os
import sys
import yaml
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feed_parser import fetchAllFeeds
from src.summarizer import summarizeDigest, summarizeWeekly, summarizeMarkets, summarizeSports, makeSpokenVersion
from src.sports import fetchMatches, fetchStandings, fetchEspnGames, buildSportsBriefText
from src.tts import generateAudio
from src.telegram import sendMessage, sendAudio
from src.vault import saveDigestArticles, saveLatestBrief


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


def runSports():
    """Sports pipeline: fetch match data → AI summarize → TTS → deliver."""
    print("=" * 60)
    print(f"DailyUpdates [sports] — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    config = loadConfig()
    settings = config.get("settings", {})
    sportsConfig = settings.get("sports", {})
    competitions = sportsConfig.get("competitions", ["WC", "PL", "MLS"])
    standingsComps = sportsConfig.get("standings_competitions", ["WC"])
    espnLeagues = sportsConfig.get("espn_leagues", ["nba", "nfl"])
    windowDays = sportsConfig.get("match_window_days", 2)

    now = datetime.now()
    dateFrom = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    dateTo = (now + timedelta(days=windowDays)).strftime("%Y-%m-%d")

    # --- Step 1: Fetch match data ---
    print(f"\n[Step 1/4] Fetching matches ({dateFrom} to {dateTo})...")
    matches = fetchMatches(dateFrom=dateFrom, dateTo=dateTo, competitionCodes=competitions)
    print(f"  Found {len(matches)} soccer matches")

    # --- Fetch NBA/NFL games from ESPN ---
    for league in espnLeagues:
        games = fetchEspnGames(league, dateFrom=dateFrom, dateTo=dateTo)
        print(f"  Found {len(games)} {league.upper()} games")
        matches.extend(games)

    # --- Filter to favorite teams (if configured) ---
    favTeams = sportsConfig.get("favorite_teams", [])
    if favTeams:
        matches = [
            m for m in matches
            if any(t.lower() in f"{m['homeTeam']} {m['awayTeam']}".lower() for t in favTeams)
        ]
        print(f"  {len(matches)} games after filtering to: {', '.join(favTeams)}")

    # --- Fetch standings for key competitions ---
    print("\n  Fetching standings...")
    allStandings = []
    for comp in standingsComps:
        s = fetchStandings(comp)
        if s:
            allStandings.extend(s)

    # --- Step 2: AI Summarization ---
    print("\n[Step 2/4] Generating sports brief...")
    sportsText = buildSportsBriefText(matches, allStandings if allStandings else None)
    model = settings.get("llm_model", "openai/gpt-oss-120b")
    digest = summarizeSports(sportsText, model=model)
    print(f"  Brief length: {len(digest)} chars")

    # --- Step 3: Text-to-Speech ---
    print("\n[Step 3/4] Generating audio...")
    voice = settings.get("tts_voice", "en-US-GuyNeural")
    spokenText = makeSpokenVersion(digest, config.get("categories", {}))
    audioPath = generateAudio(spokenText, voice=voice)

    # --- Step 4: Deliver via Telegram ---
    print("\n[Step 4/4] Sending to Telegram...")
    dateStr = datetime.now().strftime("%B %d, %Y")
    header = "🏀🏈 *Sports Brief — " + dateStr + "*\n"
    fullMessage = header + "\n" + digest
    result = sendMessage(fullMessage)
    if result.get("ok"):
        print("  Text message sent!")
    else:
        print(f"  [ERROR] Text send failed: {result}")

    tips = (
        "────────────────────\n"
        "\U0001f3a7 Audio version is below\n\n"
        "Commands:\n"
        "/sports — Match day update\n"
        "/brief — Full daily brief\n"
        "/markets — Pre-market brief\n"
        "/weekly — Week in review"
    )
    sendMessage(tips, parseMode="Markdown")

    audioResult = sendAudio(audioPath, caption=f"\U0001f3a7 Listen to today's sports brief ({datetime.now().strftime('%b %d')})")
    if audioResult.get("ok"):
        print("  Audio sent!")
    else:
        print(f"  [ERROR] Audio send failed: {audioResult}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


def run(categoryFilter: list[str] = None, mode: str = "daily"):
    """Main pipeline: fetch → summarize → TTS → deliver.

    Args:
        categoryFilter: Optional list of category keys to include. None = all.
        mode: 'daily' (default), 'weekly', 'markets', or 'sports'
    """
    if mode == "sports":
        return runSports()

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
        saveLatestBrief("No new updates found today.", mode, 0)
        return

    # --- Save article index (for /save and /research commands) ---
    print("\n  Saving article index for /save and /research commands...")
    saveDigestArticles(articlesByCategory, categories)

    # --- Step 2: AI Summarization ---
    print(f"\n[Step 2/4] Generating AI summary ({mode} mode)...")
    model = settings.get("llm_model", "openai/gpt-oss-120b")

    if mode == "weekly":
        digest = summarizeWeekly(articlesByCategory, categories, model=model)
    elif mode == "markets":
        digest = summarizeMarkets(articlesByCategory, categories, model=model)
    else:
        digest = summarizeDigest(articlesByCategory, categories, model=model)

    print(f"  Digest length: {len(digest)} chars")
    saveLatestBrief(digest, mode, totalArticles)

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
        "/sports — Match day update\n"
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
