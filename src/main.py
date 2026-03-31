"""DailyUpdates — main orchestrator.

Pipeline: Fetch RSS → AI Summarize → TTS Audio → Deliver via Telegram
"""

import os
import sys
import yaml
from datetime import datetime

# Add project root to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feed_parser import fetchAllFeeds
from src.summarizer import summarizeDigest, makeSpokenVersion
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


def run():
    """Main pipeline: fetch → summarize → TTS → deliver."""
    print("=" * 60)
    print(f"DailyUpdates — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # --- Load Config ---
    config = loadConfig()
    settings = config.get("settings", {})
    categories = config.get("categories", {})

    # --- Step 1: Fetch RSS Feeds ---
    print("\n[Step 1/4] Fetching RSS feeds...")
    articlesByCategory = fetchAllFeeds(config)

    totalArticles = sum(len(a) for a in articlesByCategory.values())
    if totalArticles == 0:
        print("\nNo articles found. Sending a 'quiet day' message.")
        sendMessage("No new updates today. Quiet day! \U0001f60e")
        return

    # --- Save article index (for /save and /research commands) ---
    print("\n  Saving article index for /save and /research commands...")
    saveDigestArticles(articlesByCategory, categories)

    # --- Step 2: AI Summarization ---
    print("\n[Step 2/4] Generating AI summary...")
    model = settings.get("llm_model", "llama-3.3-70b-versatile")
    digest = summarizeDigest(articlesByCategory, categories, model=model)
    print(f"  Digest length: {len(digest)} chars")

    # --- Step 3: Text-to-Speech ---
    print("\n[Step 3/4] Generating audio...")
    voice = settings.get("tts_voice", "en-US-GuyNeural")
    spokenText = makeSpokenVersion(digest, categories)
    audioPath = generateAudio(spokenText, voice=voice)

    # --- Step 4: Deliver via Telegram ---
    print("\n[Step 4/4] Sending to Telegram...")

    # Send the text digest
    header = f"\U0001f4f0 *Daily Brief — {datetime.now().strftime('%B %d, %Y')}*\n"
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
        "/brief — Request a new update anytime"
    )
    sendMessage(tips, parseMode="Markdown")

    # Send the audio file
    audioResult = sendAudio(audioPath, caption=f"\U0001f3a7 Listen to today's brief ({datetime.now().strftime('%b %d')})")
    if audioResult.get("ok"):
        print("  Audio sent!")
    else:
        print(f"  [ERROR] Audio send failed: {audioResult}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    run()
