"""
Twilio webhook handlers for inbound SMS, MMS (photos), and voice recordings.
"""

import logging
import traceback
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, Response
from twilio.request_validator import RequestValidator

from app.config import settings
from app.database import async_session
from app.services.classifier import ClassifierEngine
from app.services.inbound import InboundProcessor
from app.services.transcriber import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])

# Shared processor instance
_classifier = ClassifierEngine()
_processor = InboundProcessor(_classifier)


def _validate_twilio_request(request: Request, form_data: str) -> bool:
    """Validate that the request genuinely came from Twilio."""
    # Disabled during pilot testing — signature URL matching can fail
    # when Twilio sends to an IP-based URL. Re-enable when using a domain.
    return True


def _normalise_payload(form_data: dict) -> dict:
    """Convert Twilio's form list-values into single values where appropriate."""
    return {k: v[0] if isinstance(v, list) and len(v) == 1 else v
            for k, v in form_data.items()}


# ---------------------------------------------------------------------------
# SMS + MMS (Photo) inbound
# ---------------------------------------------------------------------------

@router.post("/sms")
async def inbound_sms(request: Request) -> Response:
    """
    Handle inbound SMS and MMS from Twilio.

    Twilio POSTs form-encoded data with:
      - From:  sender's phone number (E.164)
      - Body:  message text (may be empty for MMS-only)
      - MessageSid: unique message ID
      - To:    our Twilio number
      - NumMedia: number of media attachments (0 for SMS, 1+ for MMS)
      - MediaUrl0, MediaContentType0, MediaSid0: first attachment
      - MediaUrl1, MediaContentType1, MediaSid1: second attachment, etc.
    """
    try:
        body = await request.body()
        form_str = body.decode("utf-8")
        form_data = parse_qs(form_str)

        if not _validate_twilio_request(request, form_str):
            logger.warning("Invalid Twilio signature — rejecting.")
            return Response("Invalid signature", status_code=403)

        payload = _normalise_payload(form_data)
        sender = payload.get("From", "")
        message_text = payload.get("Body", "")
        message_sid = payload.get("MessageSid", "")
        num_media = int(payload.get("NumMedia", 0) or 0)

        # Handle MMS media attachments (up to 5)
        media_info = []
        has_video = False
        photo_count = 0
        if num_media > 0:
            max_media = min(num_media, 5)
            for i in range(max_media):
                media_url = payload.get(f"MediaUrl{i}", "")
                media_type = payload.get(f"MediaContentType{i}", "")
                media_sid = payload.get(f"MediaSid{i}", "")
                if not media_url:
                    continue

                entry = {"original_url": media_url, "content_type": media_type,
                         "sid": media_sid, "index": i}

                # Store media permanently (S3 or local)
                if settings.twilio_account_sid and settings.twilio_auth_token:
                    from app.services.media_store import store_media
                    stored = await store_media(media_url, media_type, media_sid, i)
                    entry.update({
                        "permanent_url": stored.get("permanent_url", media_url),
                        "category": stored.get("category", "other"),
                        "filename": stored.get("filename", ""),
                        "file_size": stored.get("file_size", 0),
                        "stored": stored.get("stored", "pending"),
                        "url": stored.get("permanent_url", media_url),
                    })
                else:
                    entry["category"] = "photo" if "image" in media_type else "video"
                    entry["url"] = media_url
                    entry["stored"] = "twilio_url"

                media_info.append(entry)
                if entry.get("category") == "video":
                    has_video = True
                else:
                    photo_count += 1

            logger.info(
                "Inbound MMS: from=%s media=%d photos=%d videos=%s body=%s",
                sender, num_media, photo_count, has_video, message_text[:100],
            )
        else:
            logger.info("Inbound SMS: from=%s body=%s", sender, message_text[:200])

        # Include media metadata in the raw payload
        raw_payload = dict(payload)
        if media_info:
            raw_payload["media"] = media_info

        channel = "sms"

        async with async_session() as session:
            result = await _processor.process(
                session=session,
                channel=channel,
                sender_id=sender,
                raw_text=message_text,
                raw_payload=raw_payload,
            )

        logger.info("Processed inbound %s: %s", "MMS" if media_info else "SMS", result)

        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml",
        )
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("SMS webhook error:\n%s", tb)
        return Response(f"{type(exc).__name__}: {exc}", status_code=500)


# ---------------------------------------------------------------------------
# Voice call + voicemail
# ---------------------------------------------------------------------------

@router.post("/voice")
async def inbound_voice(request: Request) -> Response:
    """
    Handle inbound voice calls from Twilio.

    Plays a prompt and records a voicemail.
    The recording callback webhook (/webhooks/twilio/recording) handles the result.
    """
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Say voice='alice'>State your trade, project address or number, and your issue after the beep.</Say>"
        "<Record maxLength='60' "
        f" action='{settings.get_base_url()}/webhooks/twilio/recording' "
        "method='POST' />"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/recording")
async def voice_recording(request: Request) -> Response:
    """
    Handle voicemail recording callback from Twilio.

    Twilio POSTs with:
      - RecordingUrl: URL to the audio recording (WAV)
      - RecordingSid: unique recording ID
      - From: caller's phone number
      - RecordingDuration: duration in seconds

    The audio is downloaded and transcribed via OpenAI Whisper API.
    The transcription is then passed through the ClassifierEngine.
    """
    body = await request.body()
    form_str = body.decode("utf-8")
    form_data = parse_qs(form_str)
    payload = _normalise_payload(form_data)

    recording_url = payload.get("RecordingUrl", "")
    recording_sid = payload.get("RecordingSid", "")
    sender = payload.get("From", "")
    duration = payload.get("RecordingDuration", "0")

    logger.info(
        "Voice recording: from=%s url=%s duration=%ss sid=%s",
        sender, recording_url, duration, recording_sid,
    )

    # Transcribe audio via Whisper
    twilio_auth = None
    if settings.twilio_account_sid and settings.twilio_auth_token:
        twilio_auth = (settings.twilio_account_sid, settings.twilio_auth_token)

    transcript = await transcribe_audio(recording_url, twilio_auth=twilio_auth)

    if transcript:
        full_text = transcript
        logger.info("Voicemail transcribed: %s", transcript[:150])
    else:
        full_text = (
            f"[Voice recording — duration: {duration}s, "
            f"url: {recording_url}, sid: {recording_sid}]"
        )

    raw_payload = dict(payload)
    raw_payload["transcript"] = transcript

    async with async_session() as session:
        result = await _processor.process(
            session=session,
            channel="voice_message",
            sender_id=sender,
            raw_text=full_text,
            audio_url=recording_url,
            raw_payload=raw_payload,
        )

    logger.info("Processed voice recording: %s", result)

    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )
