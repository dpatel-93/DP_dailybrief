"""Telegram delivery — sends digest text + audio via Telegram Bot API."""

import os
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _getConfig() -> tuple[str, str]:
    """Get Telegram bot token and chat ID from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chatId = os.environ.get("TELEGRAM_CHAT_ID")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not chatId:
        raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
    return token, chatId


def sendMessage(text: str, parseMode: str = "Markdown") -> dict:
    """Send a text message to the configured Telegram chat.

    Telegram has a 4096 char limit per message, so we split if needed.
    """
    token, chatId = _getConfig()
    baseUrl = TELEGRAM_API.format(token=token)

    # Split into chunks if too long (keep at 4000 to leave room for formatting)
    chunks = _splitMessage(text, maxLen=4000)
    results = []

    for chunk in chunks:
        resp = httpx.post(
            f"{baseUrl}/sendMessage",
            json={
                "chat_id": chatId,
                "text": chunk,
                "parse_mode": parseMode,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        result = resp.json()
        if not result.get("ok"):
            # Retry without parse_mode if markdown fails
            print(f"  [WARN] Markdown send failed, retrying as plain text...")
            resp = httpx.post(
                f"{baseUrl}/sendMessage",
                json={
                    "chat_id": chatId,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            result = resp.json()
        results.append(result)

    return results[-1] if results else {}


def sendAudio(filePath: str, caption: str = "Daily Brief - Audio") -> dict:
    """Send an audio file (MP3) to the configured Telegram chat."""
    token, chatId = _getConfig()
    baseUrl = TELEGRAM_API.format(token=token)

    with open(filePath, "rb") as f:
        resp = httpx.post(
            f"{baseUrl}/sendAudio",
            data={
                "chat_id": chatId,
                "caption": caption,
                "title": "Daily Brief",
                "performer": "DailyUpdates Bot",
            },
            files={"audio": ("daily_brief.mp3", f, "audio/mpeg")},
            timeout=60,
        )

    result = resp.json()
    if not result.get("ok"):
        print(f"  [ERROR] Failed to send audio: {result}")
    return result


def _splitMessage(text: str, maxLen: int = 4000) -> list[str]:
    """Split a message into chunks, trying to break at newlines."""
    if len(text) <= maxLen:
        return [text]

    chunks = []
    while text:
        if len(text) <= maxLen:
            chunks.append(text)
            break

        # Find the last newline before the limit
        splitAt = text.rfind("\n", 0, maxLen)
        if splitAt == -1:
            splitAt = maxLen

        chunks.append(text[:splitAt])
        text = text[splitAt:].lstrip("\n")

    return chunks
