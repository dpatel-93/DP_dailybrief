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
            lines.append(f"{i}. **{a.title}** ({a.source})")
            lines.append(f"   Link: {a.link}")
            lines.append(f"   Raw summary: {a.summary[:300]}")
        sections.append("\n".join(lines))

    return "\n".join(sections)


SYSTEM_PROMPT = """You are a concise news briefing assistant for a Cloud Infrastructure Engineer who manages Azure environments and follows AI and financial markets. Create a daily digest that is:
- Scannable: headlines first, then 1-sentence summaries
- Actionable: tell me WHY each story matters to someone managing Azure infra
- Grouped by category with clear section headers
- Written in a conversational but professional tone (like a smart colleague giving you the morning rundown)
- MERGE related Azure subcategories into broader sections to keep it tight

The reader cares about: Azure networking (VNets, NSGs, WAF, Front Door, App Gateway, ExpressRoute), security (Defender, Sentinel, Entra, Conditional Access), apps (Web Apps, Functions, Logic Apps, APIM, Container Apps, AKS), data (Storage, Key Vault, ADF, Databricks, ADLS), AI/Copilot (GitHub Copilot, M365 Copilot, AI Gateway, Claude, Gemini), AI security threats, financial markets (indices, futures, commodities), US/world news, and health/safety alerts (CDC, FDA recalls, children's health).

Format your output in these grouped sections (merge subcategories):

<EMOJI> <SECTION NAME>

1. <HEADLINE>
<1 sentence: what happened + why it matters>
🔗 <link>

End with a one-liner "Bottom Line" that captures the day's theme.

CRITICAL RULES:
- Keep each summary to 1 sentence MAX
- Deduplicate: if the same story appears in multiple feeds, include it only once
- Skip low-value items (minor SDK patches, routine maintenance notices)
- Prioritize: breaking changes > new features > enhancements > blog posts
- Max 3-5 items per section, even if more articles are provided
- Group into ~6-8 sections: Azure Infra, Azure Security, AI & Copilot, Cyber/AI Security, Markets, News, Health/Recalls
- Total output should be under 4000 characters"""


def summarizeDigest(
    articlesByCategory: dict[str, list[Article]],
    categoryConfigs: dict,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    """Send articles to Groq and get back a formatted digest."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        raise ValueError("GROQ_API_KEY environment variable is required")

    client = Groq(api_key=apiKey)
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


def makeSpokenVersion(digest: str, categoryConfigs: dict) -> str:
    """Convert the digest into a TTS-friendly script (no markdown, no emojis, no URLs)."""
    apiKey = os.environ.get("GROQ_API_KEY")
    if not apiKey:
        # Fallback: strip markdown manually
        return _stripForSpeech(digest)

    client = Groq(api_key=apiKey)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
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


def _stripForSpeech(text: str) -> str:
    """Fallback: rough strip of markdown/emojis for TTS."""
    import re
    text = re.sub(r"[*_#`]", "", text)
    text = re.sub(r"🔗\s*https?://\S+", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s.,;:!?'\"-]", "", text)
    return text.strip()
