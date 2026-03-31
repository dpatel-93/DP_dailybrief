# DailyUpdates

Automated daily news brief delivered to Telegram with AI-powered summaries and audio narration.

**Pipeline:** RSS Feeds → Groq AI Summary → Edge TTS Audio → Telegram

**Cost: $0/month** — all services used are free tier.

## What You Get

Every morning at 7am EST, you receive a Telegram message with:
- Headlines + 1-2 line summaries grouped by category (Azure, AI, Stocks)
- Clickable links to full articles
- An audio file you can listen to instead of reading

## Setup (5 minutes)

### 1. Create a Telegram Bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow prompts, pick a name
3. Copy the **bot token** (looks like `123456:ABC-DEF...`)
4. **Get your Chat ID**: Send any message to your new bot, then visit:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Look for `"chat":{"id": 123456789}` — that number is your Chat ID

### 2. Get a Groq API Key (free)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (no credit card needed)
3. Create an API key

### 3. Add GitHub Secrets

In your GitHub repo → Settings → Secrets and variables → Actions, add:

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

### 4. Enable the Workflow

Push to GitHub. The workflow runs daily at 7am EST automatically.

**To trigger manually:** Go to Actions → "Daily Brief" → "Run workflow"

## Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# Run
python -m src.main
```

## Customize

Edit `config.yaml` to:
- Add/remove RSS feeds
- Change categories
- Adjust articles per category
- Change TTS voice
- Change schedule time

## Architecture

```
config.yaml          — feeds + settings
src/
  main.py            — orchestrator
  feed_parser.py     — RSS fetch + parse + dedup
  summarizer.py      — Groq AI summarization
  tts.py             — edge-tts audio generation
  telegram.py        — Telegram Bot API delivery
.github/workflows/
  daily-brief.yml    — cron schedule + manual trigger
```

## Free Services Used

| Service | What For | Free Tier |
|---|---|---|
| GitHub Actions | Scheduling + compute | Unlimited (public repo) |
| Groq | AI summarization (Llama 3.3 70B) | 500K tokens/day |
| edge-tts | Text-to-speech (Microsoft neural) | Unlimited, no API key |
| Telegram Bot API | Message delivery | Unlimited |
