# DailyUpdates

Automated daily news brief delivered to Telegram with AI-powered summaries, audio narration, and Obsidian vault integration.

**Pipeline:** RSS Feeds → Groq AI Summary → Edge TTS Audio → Telegram → Obsidian

**Cost: $0/month** — all services used are free tier.

## What You Get

Every morning at 8am EST, you receive a Telegram message with:
- Headlines + 1-sentence summaries grouped by category
- Clickable links to full articles
- Audio file (British Ryan voice) you can listen to instead of reading
- Commands to save or research any article into your Obsidian vault

## Telegram Commands

| Command | What It Does |
|---|---|
| `/brief` | Generate a new digest on demand |
| `/list` | Show all articles by number from the last digest |
| `/save <number>` | Save an article as a bookmark note in Obsidian |
| `/research <number>` | AI deep-dive on an article, saved to Obsidian |
| `/save all` | Save the full digest as one Obsidian note |

## RSS Feeds (65+ sources across 15 categories)

### Azure Infrastructure & Platform

| Category | Feeds |
|---|---|
| **Azure Networking** | Azure Networking Blog, Azure Network Security, Azure Front Door |
| **Azure Security & Identity** | Microsoft Sentinel, Defender for Cloud, Microsoft Entra, Core Infra & Security, Microsoft Security Blog |
| **Azure Apps & Serverless** | Apps on Azure, Azure Web Apps, Azure Functions, Azure Logic Apps, Azure APIM |
| **Azure Containers & AKS** | AKS Blog, Azure Containers, AKS GitHub Releases |
| **Azure Data & Storage** | Azure Storage, Azure Data Factory, Azure Databricks, Azure Synapse, Key Vault |
| **Azure Platform Updates** | Azure Release Communications, Azure Blog, Azure SDK Blog, Azure Governance |

### AI, Copilot & Security

| Category | Feeds |
|---|---|
| **AI & Copilot** | GitHub Copilot Changelog, GitHub Blog, M365 Copilot, Microsoft AI Blog, APIM / AI Gateway |
| **AI Industry News** | OpenAI News, Google Gemini, Google AI Blog, MarkTechPost, TechCrunch AI |
| **AI Security & Threats** | Microsoft Security Blog, Google Security Blog, BleepingComputer, The Hacker News, Krebs on Security |

### Markets & Finance

| Category | Feeds |
|---|---|
| **Market News & Indices** | Investing.com Stocks, Investing.com Indices Analysis, Investing.com All News, MarketWatch Top Stories, Seeking Alpha |
| **Futures & Commodities** | Investing.com Futures, Investing.com Energy, Investing.com Metals, Investing.com Economy, Investing.com Editor's Picks |

### News & World Affairs

| Category | Feeds |
|---|---|
| **US & Breaking News** | NPR Top Stories, NPR Politics, PBS NewsHour |
| **World News** | BBC World, BBC Top Stories, Al Jazeera, NPR World |

### Health, Safety & Recalls

| Category | Feeds |
|---|---|
| **Health & Safety Alerts** | CDC Newsroom, CDC Outbreaks, CDC Kids Health, NPR Health |
| **Product & Food Recalls** | CPSC All Recalls, CPSC Children's Recalls, FDA Food Recalls, FDA MedWatch Alerts |

## How to Add/Change Feeds

Edit `config.yaml`. Each category follows this structure:

```yaml
categories:
  my_category:
    name: "Display Name"       # Shown in the digest header
    emoji: "\U0001f4f0"        # Emoji for the category
    feeds:
      - url: "https://example.com/feed.xml"
        name: "Source Name"    # Shown next to article titles
      - url: "https://another.com/rss"
        name: "Another Source"
```

### Adding a new feed to an existing category

Add a new `- url:` / `name:` block under the category's `feeds:` list.

### Adding a new category

Copy an existing category block, change the key (`my_category`), name, emoji, and feeds.

### Changing how many articles per category

Edit `settings.articles_per_category` in `config.yaml` (default: 5).

### Changing the voice

Edit `settings.tts_voice` in `config.yaml`. Options:

| Voice ID | Style |
|---|---|
| `en-GB-RyanNeural` | British male (current) |
| `en-US-GuyNeural` | American male |
| `en-US-AriaNeural` | American female |
| `en-US-DavisNeural` | Calm male |
| `en-US-JennyNeural` | Friendly female |

### Changing the schedule

Edit the cron in `.github/workflows/daily-brief.yml`. The time is in UTC.
- `0 12 * * *` = 8am EST / 8am EDT (current)
- `0 13 * * *` = 9am EST
- `0 22 * * *` = 6pm EST

### Finding RSS feeds

Most blogs have an RSS feed. Common patterns:
- `/feed/`, `/rss/`, `/rss.xml`, `/feed.xml`, `/atom.xml`
- TechCommunity: `https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=<BOARD_ID>`
- GitHub repos: `https://github.com/<owner>/<repo>/releases.atom`

## Setup

### 1. Create a Telegram Bot

1. Open Telegram → search `@BotFather` → `/newbot`
2. Copy the **bot token**
3. Send any message to your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to get your **Chat ID**

### 2. Get a Groq API Key (free)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (no credit card) → Create API key

### 3. Create a GitHub PAT for Obsidian vault (optional)

Only needed if you want `/save` and `/research` commands:
1. github.com → Settings → Developer settings → Fine-grained tokens
2. Repo access: `DP_Obsidian_Vault` only → Contents: Read+Write

### 4. Add GitHub Secrets

| Secret | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | AI summarization |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram delivery |
| `TELEGRAM_CHAT_ID` | Yes | Your Telegram chat |
| `VAULT_PAT` | Optional | Push notes to Obsidian vault repo |

### 5. Run Locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python -m src.main
```

## Architecture

```
config.yaml                          — feeds, categories, settings
data/last_digest.json                — article index for /save and /research
src/
  main.py                            — orchestrator (fetch → summarize → TTS → deliver)
  feed_parser.py                     — RSS fetch, parse, dedup, rank
  summarizer.py                      — Groq AI summarization + spoken script
  tts.py                             — edge-tts audio generation (MP3)
  telegram.py                        — Telegram Bot API (text + audio)
  bot_commands.py                    — command parser (/brief, /save, /research, /list)
  check_commands.py                  — command dispatcher (entry point for listener)
  vault.py                           — Obsidian vault integration (GitHub API push)
.github/workflows/
  daily-brief.yml                    — 8am EST cron + manual trigger
  telegram-listener.yml              — polls every 30 min for bot commands
```

## Free Services Used

| Service | Purpose | Free Tier |
|---|---|---|
| GitHub Actions | Scheduling + compute | 2,000 min/mo (private repo) |
| Groq | AI summarization (Llama 3.3 70B) | 500K tokens/day |
| edge-tts | Text-to-speech (Microsoft neural) | Unlimited, no API key |
| Telegram Bot API | Message delivery | Unlimited |
| GitHub API | Push notes to Obsidian vault | 5,000 requests/hour |
