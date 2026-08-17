"""AI summarizer — uses Groq (free tier) to create a concise daily brief."""

import os
from groq import Groq
from src.feed_parser import Article


def buildPrompt(articlesByCategory: dict[str, list[Article]], categoryConfigs: dict) -> str:
    """Build the prompt with all articles for the LLM to summarize."""
    sections = []
    for key, articles in articlesByCategory.items():
        if not articles:
            continue
        catName = categoryConfigs[key]["name"]
        lines = [f"\n## {catName}"]
        for i, a in enumerate(articles, 1):
            tags = []
            if a.isPriority:
                tags.append(f"PRIORITY({', '.join(a.priorityMatches[:3])})")
            if a.trendingTopic:
                tags.append("TRENDING")
            tagStr = f" [{' | '.join(tags)}]" if tags else ""
            lines.append(f"{i}. **{a.title}**{tagStr} ({a.source})")
            lines.append(f"   Link: {a.link}")
            lines.append(f"   Raw summary: {a.summary[:300]}")
        sections.append("\n".join(lines))

    return "\n".join(sections)


SYSTEM_PROMPT = """Do not use web search, code execution, or any other tool — work only from the article text given to you below.

You are a concise news briefing assistant for Dishi, a Cloud Infrastructure Engineer (8 years Azure) who manages enterprise Azure environments and follows AI, security, and financial markets. Create a daily digest that is:
- Scannable: headlines first, then 1-sentence summaries
- Actionable: tell me WHY each story matters to someone managing Azure infra
- Grouped by category with clear section headers
- Written in a conversational but professional tone (like a smart colleague giving you the morning rundown)
- MERGE related Azure subcategories into broader sections to keep it tight

PERSONAL RELEVANCE — prioritize stories about:
HIGH: Azure networking (VNets, NSGs, WAF, Front Door, App Gateway, ExpressRoute, Private Link), security (Defender, Sentinel, Entra, Conditional Access), breaking changes, deprecations, CVEs
MEDIUM: Apps (Web Apps, Functions, Logic Apps, APIM, Container Apps, AKS), data (Storage, Key Vault, ADF, Databricks), AI sector (models, capabilities, AND AI security incidents — breaches, model vulnerabilities, prompt injection, misuse), cloud industry trends
NORMAL: Markets, world news, health/recalls

SPECIAL MARKERS in the input:
- [PRIORITY(keyword)] = matches Dishi's priority keywords — these should appear FIRST in their section
- [TRENDING] = multiple sources are reporting this — call it out as a developing story

Format your output in these grouped sections (merge subcategories):

🔥 TRENDING (only if there are trending stories — lead with these)

<EMOJI> <SECTION NAME>

⭐ 1. <HEADLINE> (star = priority match)
<1 sentence: what happened + why it matters>
🔗 <link>

End with a one-liner "Bottom Line" that captures the day's theme.

CRITICAL RULES:
- Keep each summary to 1 sentence MAX
- Deduplicate: if the same story appears in multiple feeds, include it only once
- Skip low-value items (minor SDK patches, routine maintenance notices)
- Prioritize: breaking changes > security advisories > new features > enhancements > blog posts
- Include up to 5 items per section (aim for 5 when enough quality stories exist, even if more articles are provided)
- Group into ~6-8 sections: Azure Infra, Azure Security, Cloud & DevOps, AI Sector (models, capabilities & AI security incidents), Cyber/SecOps, Markets, News, Health/Recalls
- Total output should be under 4000 characters
- Star (⭐) priority items"""


def summarizeDigest(
    articlesByCategory: dict[str, list[Article]],
    categoryConfigs: dict,
    model: str = "groq/compound-mini",
) -> str:
    """Send articles to Groq and get back a formatted digest."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        raise ValueError("GROQ_API_KEY environment variable is required")

    client = Groq(api_key=apiKey, max_retries=5)
    articleText = buildPrompt(articlesByCategory, categoryConfigs)

    if not articleText.strip():
        return "No new articles found in the last 24 hours. Quiet day!"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Create today's daily brief from these articles:\n{articleText}",
            },
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    return response.choices[0].message.content


WEEKLY_SYSTEM_PROMPT = """Do not use web search, code execution, or any other tool — work only from the article text given to you below.

You are a weekly news briefing assistant for Dishi, a Cloud Infrastructure Engineer (8 years Azure). Create a WEEKLY digest that:
- Covers the TOP stories from the entire week
- Groups by theme, not chronology
- Highlights patterns and trends across the week
- Calls out the 3 most important things Dishi should know
- Written in a conversational but professional tone

Format:
🏆 TOP 3 THIS WEEK
1. <headline + 2 sentence summary>
2. <headline + 2 sentence summary>
3. <headline + 2 sentence summary>

Then sections for: Azure, AI, Security, Markets, News
- Max 3 items per section
- Focus on what CHANGED this week, not routine updates
- Under 5000 characters total"""


def summarizeWeekly(
    articlesByCategory: dict[str, list[Article]],
    categoryConfigs: dict,
    model: str = "groq/compound-mini",
) -> str:
    """Create a weekly summary from the week's articles."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        raise ValueError("GROQ_API_KEY environment variable is required")

    client = Groq(api_key=apiKey, max_retries=5)
    articleText = buildPrompt(articlesByCategory, categoryConfigs)

    if not articleText.strip():
        return "Quiet week — no notable articles found."

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": WEEKLY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Create this week's summary from these articles:\n{articleText}",
            },
        ],
        temperature=0.3,
        max_tokens=5000,
    )

    return response.choices[0].message.content


MARKETS_SYSTEM_PROMPT = """Do not use web search, code execution, or any other tool — work only from the article text given to you below.

You are a pre-market briefing assistant for a trader who follows futures, indices, commodities, and crypto. Create a QUICK pre-market brief that:
- Opens with futures snapshot (S&P, Nasdaq, Dow, Russell)
- Covers key movers and why
- Notes any macro events today (Fed, earnings, data releases)
- Mentions crypto highlights if notable
- Tone: direct, no fluff, numbers-first
- Under 2000 characters
- End with "Watch for:" with 2-3 things to monitor today"""


def summarizeMarkets(
    articlesByCategory: dict[str, list[Article]],
    categoryConfigs: dict,
    model: str = "groq/compound-mini",
) -> str:
    """Create a pre-market morning brief focused on markets only."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        raise ValueError("GROQ_API_KEY environment variable is required")

    client = Groq(api_key=apiKey, max_retries=5)
    articleText = buildPrompt(articlesByCategory, categoryConfigs)

    if not articleText.strip():
        return "No market news available right now."

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MARKETS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Create a pre-market brief from these articles:\n{articleText}",
            },
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def makeSpokenVersion(digest: str, categoryConfigs: dict) -> str:
    """Convert the digest into a TTS-friendly script (no markdown, no emojis, no URLs)."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        return _stripForSpeech(digest)

    client = Groq(api_key=apiKey, max_retries=5)

    response = client.chat.completions.create(
        model="groq/compound-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Do not use web search, code execution, or any other tool — work only from the digest text given to you. "
                    "Convert this news digest into a spoken script for text-to-speech. "
                    "Rules: No emojis, no URLs, no markdown formatting, no special characters. "
                    "Use natural speech transitions like 'Moving on to...' or 'In AI news today...'. "
                    "Start with 'Good morning! Here is your daily brief for today.' "
                    "End with the bottom line summary and 'That is your update. Have a great day!'. "
                    "Keep it concise — under 3 minutes when read aloud. "
                    "Group Azure updates together, then AI, then markets."
                ),
            },
            {"role": "user", "content": digest},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    return response.choices[0].message.content


SPORTS_SYSTEM_PROMPT = """Do not use web search, code execution, or any other tool — work only from the match data given to you below.

You are a sports briefing assistant covering soccer (World Cup, Champions League, Premier League, La Liga, Bundesliga, Serie A, Ligue 1 — especially Inter Miami), the NBA, and the NFL. Create a match day brief that:
- Leads with LIVE games if any are in progress
- Shows yesterday's/today's results with scorelines and notable moments
- Lists upcoming games with the FULL DATE and EXACT start time in Eastern Time (ET) — always include the day of week and date (e.g., "Thu Jun 11, 3:00 PM ET"), never just the time
- For each upcoming game, note the broadcast channel. The input data already includes "TV:" info for NBA/NFL games — use it verbatim. For soccer, infer the channel (the user has a Fox subscription)
- Highlights World Cup matches above all else — these are MUST-WATCH
- Calls out upsets, overtime thrillers, hat tricks, red cards, dramatic finishes, buzzer-beaters
- Includes standings context where relevant (e.g., "top of Group A", "fighting for 4th")
- Tone: passionate but concise, like a knowledgeable friend giving you the rundown before your day

Format with one section PER SPORT (only include sports that have games):

⚽ SOCCER
🏀 NBA
🏈 NFL

Within each sport, organize as:

LIVE (only if games in progress)
<game details with current score>

RESULTS
<scorelines, note any standout performances>

UPCOMING — WHAT TO WATCH
For each game:
<Day, Date, Time ET> | <Away> @ <Home> | <League> | <Channel>
<One line: why this game matters or who to watch>

🏆 STANDINGS (soccer only — show top 4-5 of relevant tables)

End with a "🎯 Don't Miss:" one-liner highlighting the single best game to watch across all sports.

RULES:
- World Cup matches get priority placement and more detail
- Flag Inter Miami matches with 🌴 emoji
- ALWAYS include the day of week + date for every upcoming game, not just the time
- All times must be in Eastern Time (ET)
- For soccer broadcast info: FIFA World Cup → FOX/FS1/FS2, Premier League → USA Network/Peacock, Champions League → CBS/Paramount+, La Liga → ESPN+, Bundesliga → ESPN+, Serie A → CBS/Paramount+, Ligue 1 → beIN Sports. For NBA/NFL, use the TV info provided in the input
- Under 3800 characters total
- Use country flags for soccer where possible (🇺🇸 🇧🇷 🇦🇷 🇫🇷 🇩🇪 🇪🇸 🏴󠁧󠁢󠁥󠁮󠁧󠁿 etc.)"""


def summarizeSports(sportsText: str, model: str = "groq/compound-mini") -> str:
    """Create an AI-summarized sports brief from match data."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        return sportsText

    client = Groq(api_key=apiKey, max_retries=5)

    if not sportsText.strip() or sportsText.startswith("No upcoming"):
        return "No Knicks or Giants games this week. Off week! 🏀🏈😴"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SPORTS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Create today's football/soccer brief from this data:\n{sportsText}",
            },
        ],
        temperature=0.4,
        max_tokens=3000,
    )

    return response.choices[0].message.content


def _stripForSpeech(text: str) -> str:
    """Fallback: rough strip of markdown/emojis for TTS."""
    import re
    text = re.sub(r"[*_#`]", "", text)
    text = re.sub(r"🔗\s*https?://\S+", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s.,;:!?'\"-]", "", text)
    return text.strip()
