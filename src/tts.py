"""Text-to-Speech using edge-tts — free Microsoft neural voices, no API key needed."""

import asyncio
import edge_tts
import os


async def _generateAudio(text: str, voice: str, outputPath: str) -> str:
    """Generate MP3 audio from text using edge-tts."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(outputPath)
    return outputPath


def generateAudio(text: str, voice: str = "en-US-GuyNeural", outputDir: str = "/tmp") -> str:
    """Generate MP3 from spoken text. Returns the file path.

    Popular voice options:
      - en-US-GuyNeural      (male, natural, good for news)
      - en-US-AriaNeural     (female, natural)
      - en-US-DavisNeural    (male, calm)
      - en-US-JennyNeural    (female, friendly)
      - en-GB-RyanNeural     (male, British)
    """
    os.makedirs(outputDir, exist_ok=True)
    outputPath = os.path.join(outputDir, "daily_brief.mp3")

    print(f"  Generating audio with voice: {voice}")
    asyncio.run(_generateAudio(text, voice, outputPath))

    fileSize = os.path.getsize(outputPath)
    print(f"  Audio generated: {outputPath} ({fileSize / 1024:.0f} KB)")
    return outputPath


async def listVoices(language: str = "en") -> list[dict]:
    """List available voices for a language (useful for picking a voice)."""
    voices = await edge_tts.list_voices()
    return [v for v in voices if v["Locale"].startswith(language)]
