"""
Transcriber — Audio transcription via OpenAI Whisper API.

Downloads audio from a URL (e.g. Twilio recording) and transcribes it
using OpenAI's Whisper API. Falls back gracefully if the API key is
not configured or the download fails.
"""

import logging
import tempfile
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Maximum audio file size for Whisper API (25 MB)
MAX_FILE_SIZE = 25 * 1024 * 1024


async def transcribe_audio(audio_url: str, twilio_auth: tuple | None = None) -> str | None:
    """
    Download audio from a URL and transcribe via OpenAI Whisper API.

    Args:
        audio_url: Public or authenticated URL to the audio file.
        twilio_auth: Optional (account_sid, auth_token) tuple for
                     Twilio recording URLs that require authentication.

    Returns:
        Transcribed text, or None if transcription failed.
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured — skipping transcription.")
        return None

    # ── Download audio ──
    audio_data = await _download_audio(audio_url, twilio_auth)
    if not audio_data:
        logger.warning("Failed to download audio from %s", audio_url)
        return None

    if len(audio_data) > MAX_FILE_SIZE:
        logger.warning("Audio file too large (%d bytes) — skipping transcription.", len(audio_data))
        return None

    # ── Transcribe via Whisper API ──
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        # Write to a temp file so we can send it to the API
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                response = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text",
                )
            transcript = response.strip() if isinstance(response, str) else (response.text or "").strip()
            logger.info("Transcription complete: %s", transcript[:100])
            return transcript if transcript else None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    except ImportError:
        logger.warning("OpenAI package not installed — skipping transcription.")
        return None
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        return None


async def _download_audio(url: str, auth: tuple | None = None) -> bytes | None:
    """Download audio file from URL with optional HTTP Basic Auth."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"User-Agent": "SMS-Andon-System/1.0"}
            if auth:
                response = await client.get(url, headers=headers, auth=auth)
            else:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP error downloading audio: %s", exc)
        return None
    except httpx.RequestError as exc:
        logger.warning("Network error downloading audio: %s", exc)
        return None
