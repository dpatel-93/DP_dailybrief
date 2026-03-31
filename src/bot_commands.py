"""Telegram bot command handler — checks for /brief commands and triggers the digest."""

import os
import time
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"

# Only process messages from the last N seconds (stateless — no offset persistence needed)
MAX_MESSAGE_AGE_SECONDS = 1800  # 30 minutes (matches the polling interval)


def checkForCommands() -> list[dict]:
    """Poll Telegram for recent /brief commands. Stateless — uses message timestamps."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chatId = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chatId:
        return []

    baseUrl = TELEGRAM_API.format(token=token)
    cutoff = time.time() - MAX_MESSAGE_AGE_SECONDS

    try:
        resp = httpx.get(
            f"{baseUrl}/getUpdates",
            params={"timeout": 5, "allowed_updates": '["message"]'},
            timeout=15,
        )
        data = resp.json()
    except Exception as e:
        print(f"  [WARN] Failed to poll Telegram: {e}")
        return []

    if not data.get("ok"):
        return []

    commands = []
    maxUpdateId = 0

    for update in data.get("result", []):
        updateId = update.get("update_id", 0)
        maxUpdateId = max(maxUpdateId, updateId)

        msg = update.get("message", {})
        text = msg.get("text", "").strip().lower()
        msgTime = msg.get("date", 0)
        msgChatId = str(msg.get("chat", {}).get("id", ""))

        # Only respond to commands from the authorized chat
        if msgChatId != str(chatId):
            continue

        # Skip old messages (before our polling window)
        if msgTime < cutoff:
            continue

        if text in ["/brief", "/update", "brief", "update"]:
            commands.append(msg)
            print(f"  Found command: '{text}' at {msgTime}")

    # Acknowledge all processed updates so they don't show up again
    if maxUpdateId:
        try:
            httpx.get(
                f"{baseUrl}/getUpdates",
                params={"offset": maxUpdateId + 1, "timeout": 1},
                timeout=10,
            )
        except Exception:
            pass

    if commands:
        _sendReply(token, chatId, "Got it! Generating your brief now... \u23f3")

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
