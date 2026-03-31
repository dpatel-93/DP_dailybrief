"""Telegram bot command handler — checks for /brief commands and triggers the digest."""

import os
import json
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"
OFFSET_FILE = "/tmp/telegram_offset.txt"


def checkForCommands() -> list[dict]:
    """Poll Telegram for new /brief commands. Returns list of command messages."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chatId = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chatId:
        return []

    baseUrl = TELEGRAM_API.format(token=token)

    # Read last processed update offset (so we don't re-process old messages)
    offset = _loadOffset()

    params = {"timeout": 5, "allowed_updates": '["message"]'}
    if offset:
        params["offset"] = offset

    try:
        resp = httpx.get(f"{baseUrl}/getUpdates", params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"  [WARN] Failed to poll Telegram: {e}")
        return []

    if not data.get("ok"):
        return []

    commands = []
    maxUpdateId = offset or 0

    for update in data.get("result", []):
        updateId = update.get("update_id", 0)
        maxUpdateId = max(maxUpdateId, updateId)

        msg = update.get("message", {})
        text = msg.get("text", "").strip().lower()
        msgChatId = str(msg.get("chat", {}).get("id", ""))

        # Only respond to commands from the authorized chat
        if msgChatId != str(chatId):
            continue

        if text in ["/brief", "/update", "brief", "update"]:
            commands.append(msg)
            _sendReply(token, chatId, "Got it! Generating your brief now... ⏳")

    # Save offset so we don't reprocess these messages
    if maxUpdateId:
        _saveOffset(maxUpdateId + 1)

    return commands


def _sendReply(token: str, chatId: str, text: str):
    """Send a quick reply to the user."""
    baseUrl = TELEGRAM_API.format(token=token)
    try:
        httpx.post(
            f"{baseUrl}/sendMessage",
            json={"chat_id": chatId, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def _loadOffset() -> int | None:
    """Load the last processed Telegram update offset."""
    # Try environment variable first (for GitHub Actions, passed between runs)
    envOffset = os.environ.get("TELEGRAM_OFFSET")
    if envOffset:
        return int(envOffset)

    # Try file (for local runs)
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def _saveOffset(offset: int):
    """Save the update offset for next poll."""
    try:
        with open(OFFSET_FILE, "w") as f:
            f.write(str(offset))
    except Exception:
        pass
    # Also print it so GitHub Actions can capture it
    print(f"TELEGRAM_OFFSET={offset}")
