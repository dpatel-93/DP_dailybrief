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


SYSTEM_PROMPT = """You are a concise news briefing assistant. You create a daily digest that is:
- Scannable: headlines first, then 1-2 sentence summaries
- Actionable: tell me WHY each story matters, not just what happened
- Grouped by category with clear section headers
- Written in a conversational but professional tone (like a smart colleague giving you the morning rundown)

Format your output EXACTLY like this for each category:

<CATEGORY EMOJI> <CATEGORY NAME>

1. <HEADLINE>
<1-2 sentence summary explaining what happened and why it matters>
🔗 <link>

2. ...

End with a one-liner "Bottom Line" that captures the day's overall theme across all categories.

IMPORTANT: Keep each summary to 1-2 sentences MAX. The user wants to scan quickly, not read essays."""


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
        max_tokens=2000,
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
                    "Keep it concise — under 90 seconds when read aloud."
                ),
            },
            {"role": "user", "content": digest},
        ],
        temperature=0.3,
        max_tokens=1500,
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
