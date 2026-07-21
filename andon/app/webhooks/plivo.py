"""
Plivo webhook handlers for inbound SMS, MMS (photos), and voice recordings.

Replaces the Twilio webhooks. Routes through the same InboundProcessor
classifier pipeline — only the communication channel changes.
"""

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, Response

from app.config import settings
from app.database import async_session
from app.services.classifier import ClassifierEngine
from app.services.inbound import InboundProcessor
from app.services.transcriber import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/plivo", tags=["plivo"])

_classifier = ClassifierEngine()
_processor = InboundProcessor(_classifier)


def _normalise(payload: dict) -> dict:
    """Convert list-values to single values where appropriate."""
    return {k: v[0] if isinstance(v, list) and len(v) == 1 else v
            for k, v in payload.items()}


# ---------------------------------------------------------------------------
# SMS + MMS (Photo) inbound
# ---------------------------------------------------------------------------

@router.post("/sms")
async def inbound_sms(request: Request) -> Response:
    """
    Handle inbound SMS and MMS from Plivo.

    Plivo POSTs form-encoded data with:
      - From:     sender's phone number (E.164)
      - To:       your Plivo number
      - Text:     message text (may be empty for MMS-only)
      - MessageUUID: unique message ID
      - total_media: number of media attachments (0 for SMS, 1+ for MMS)
      - Media:    comma-separated media URLs (for MMS)
      - MediaContentType: Content-Type of media (if available)
    """
    try:
        body = await request.body()
        form_str = body.decode("utf-8")
        form_data = parse_qs(form_str)
        payload = _normalise(form_data)

        sender = payload.get("From", "")
        message_text = payload.get("Text", "")
        message_uuid = payload.get("MessageUUID", "")
        total_media = int(payload.get("total_media", 0) or 0)

        # Handle MMS media attachments
        media_info = []
        has_video = False
        photo_count = 0
        if total_media > 0:
            media_raw = payload.get("Media", "")
            content_type_raw = payload.get("MediaContentType", "")
            media_urls = media_raw.split(",") if media_raw else []
            content_types = content_type_raw.split(",") if content_type_raw else []
            for i, url in enumerate(media_urls[:5]):
                url = url.strip()
                if not url:
                    continue
                ct = content_types[i].strip() if i < len(content_types) else "image/jpeg"
                entry = {
                    "original_url": url,
                    "content_type": ct,
                    "url": url,
                    "sid": f"plivo-{message_uuid}-{i}",
                    "index": i,
                    "category": "photo" if "image" in ct else "video",
                    "stored": "plivo_url",
                }
                media_info.append(entry)
                if entry["category"] == "video":
                    has_video = True
                else:
                    photo_count += 1
            logger.info(
                "Inbound MMS: from=%s media=%d photos=%d videos=%s text=%s",
                sender, total_media, photo_count, has_video, message_text[:100],
            )
        else:
            logger.info("Inbound SMS: from=%s text=%s", sender, message_text[:200])

        raw_payload = dict(payload)
        if media_info:
            raw_payload["media"] = media_info

        async with async_session() as session:
            result = await _processor.process(
                session=session,
                channel="sms",
                sender_id=sender,
                raw_text=message_text,
                raw_payload=raw_payload,
            )

        logger.info("Processed inbound %s: %s", "MMS" if media_info else "SMS", result)
        return Response(content="OK", status_code=200)

    except Exception as exc:
        logger.exception("Plivo SMS webhook error: %s", exc)
        return Response(f"Error: {exc}", status_code=500)


# ---------------------------------------------------------------------------
# Voice call + voicemail
# ---------------------------------------------------------------------------

@router.post("/voice")
async def inbound_voice(request: Request) -> Response:
    """
    Handle inbound voice calls from Plivo.

    Plivo sends a GET or POST to this URL when a call comes in.
    We respond with Plivo XML that plays a prompt and records a voicemail.
    The recording callback is handled by /webhooks/plivo/recording.
    """
    base = settings.get_base_url()
    plivo_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Speak>You've reached the job site status line. "
        "Please leave a message after the beep describing your issue "
        "and which house you're at. Speak clearly and include the address.</Speak>"
        f"<Record action='{base}/webhooks/plivo/recording' "
        "method='POST' maxDuration='60' />"
        "</Response>"
    )
    return Response(content=plivo_xml, media_type="application/xml")


@router.post("/recording")
async def voice_recording(request: Request) -> Response:
    """
    Handle voicemail recording callback from Plivo.

    Plivo POSTs with:
      - RecordUrl: URL to the recorded audio
      - RecordDuration: duration in seconds
      - From: caller's phone number
      - CallUUID: unique call ID
    """
    body = await request.body()
    form_str = body.decode("utf-8")
    form_data = parse_qs(form_str)
    payload = _normalise(form_data)

    record_url = payload.get("RecordUrl", "")
    duration = payload.get("RecordDuration", "0")
    sender = payload.get("From", "")
    call_uuid = payload.get("CallUUID", "")

    logger.info("Voice recording: from=%s url=%s duration=%ss call=%s", sender, record_url, duration, call_uuid)

    # Transcribe via Whisper
    transcript = await transcribe_audio(record_url)

    if transcript:
        full_text = transcript
        logger.info("Voicemail transcribed: %s", transcript[:150])
    else:
        full_text = f"[Voice recording — duration: {duration}s, url: {record_url}]"

    raw_payload = dict(payload)
    raw_payload["transcript"] = transcript

    async with async_session() as session:
        result = await _processor.process(
            session=session,
            channel="voice_message",
            sender_id=sender,
            raw_text=full_text,
            audio_url=record_url,
            raw_payload=raw_payload,
        )

    logger.info("Processed voice recording: %s", result)
    return Response(content="OK", status_code=200)
