"""Telegram bot command handler — checks for commands and dispatches actions."""

import os
import re
import time
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"

# Only process messages from the last N seconds (stateless — no offset persistence needed)
MAX_MESSAGE_AGE_SECONDS = 600  # 10 minutes (2x the polling interval for buffer)


def checkForCommands() -> dict:
    """Poll Telegram for recent commands. Returns categorized commands.

    Returns dict with keys: 'brief', 'save', 'research', 'list', 'weekly', 'markets', 'queue'
    Each value is a list of command details.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chatId = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chatId:
        return {"brief": [], "save": [], "research": [], "list": [], "weekly": [], "markets": [], "sports": [], "queue": []}

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
        return {"brief": [], "save": [], "research": [], "list": [], "weekly": [], "markets": [], "sports": [], "queue": []}

    if not data.get("ok"):
        return {"brief": [], "save": [], "research": [], "list": [], "weekly": [], "markets": [], "sports": [], "queue": []}

    result = {"brief": [], "save": [], "research": [], "list": [], "weekly": [], "markets": [], "sports": [], "queue": []}
    maxUpdateId = 0

    updates = data.get("result", [])
    print(f"  Received {len(updates)} update(s) from Telegram")

    for update in updates:
        updateId = update.get("update_id", 0)
        maxUpdateId = max(maxUpdateId, updateId)

        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        textLower = text.lower()
        msgTime = msg.get("date", 0)
        msgChatId = str(msg.get("chat", {}).get("id", ""))

        if msgChatId != str(chatId):
            print(f"  Skipping update {updateId}: chat {msgChatId} != {chatId}")
            continue
        if msgTime < cutoff:
            print(f"  Skipping update {updateId}: too old ({int(time.time() - msgTime)}s ago)")
            continue

        # Normalize command — strip @botname suffix (e.g., /brief@MyBot -> /brief)
        parts = textLower.split("@")[0].split() if textLower else [""]
        normalized = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        print(f"  Processing update {updateId}: text='{textLower}' normalized='{normalized}' args={args}")

        # Parse commands
        if normalized in ["/brief", "/update", "brief", "update"]:
            # Check for category filter argument (e.g., /brief azure)
            filterArg = args[0] if args else None
            result["brief"].append({"filter": filterArg, **msg})
            print(f"  Found command: '{normalized}' filter={filterArg} at {msgTime}")

        elif normalized in ["/weekly", "weekly"]:
            result["weekly"].append(msg)
            print(f"  Found command: weekly at {msgTime}")

        elif normalized in ["/markets", "markets"]:
            result["markets"].append(msg)
            print(f"  Found command: markets at {msgTime}")

        elif normalized in ["/sports", "sports"]:
            result["sports"].append(msg)
            print(f"  Found command: sports at {msgTime}")

        elif normalized.startswith("/save") or normalized.startswith("save"):
            nums = re.findall(r"\d+", text)
            if textLower.endswith("all"):
                result["save"].append({"type": "all"})
                print(f"  Found command: save all at {msgTime}")
            elif nums:
                for n in nums:
                    result["save"].append({"type": "single", "index": int(n)})
                    print(f"  Found command: save {n} at {msgTime}")

        elif normalized.startswith("/research") or normalized.startswith("research"):
            nums = re.findall(r"\d+", text)
            for n in nums:
                result["research"].append({"index": int(n)})
                print(f"  Found command: research {n} at {msgTime}")

        elif normalized.startswith("/queue") or normalized.startswith("queue"):
            nums = re.findall(r"\d+", text)
            for n in nums:
                result["queue"].append({"index": int(n)})
                print(f"  Found command: queue {n} at {msgTime}")

        elif normalized in ["/list", "/saved", "list saved", "list"]:
            result["list"].append(msg)
            print(f"  Found command: list at {msgTime}")

    # Acknowledge all processed updates
    if maxUpdateId:
        try:
            httpx.get(
                f"{baseUrl}/getUpdates",
                params={"offset": maxUpdateId + 1, "timeout": 1},
                timeout=10,
            )
        except Exception:
            pass

    return result


def sendReply(text: str):
    """Send a reply to the configured Telegram chat."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chatId = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chatId:
        return
    baseUrl = TELEGRAM_API.format(token=token)
    try:
        httpx.post(
            f"{baseUrl}/sendMessage",
            json={"chat_id": chatId, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
    except Exception:
        pass
