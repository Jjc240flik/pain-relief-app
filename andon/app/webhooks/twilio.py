"""
Twilio webhook handlers for inbound SMS and voice.
"""

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, Response
from twilio.request_validator import RequestValidator

from app.config import settings
from app.database import async_session
from app.services.classifier import ClassifierEngine
from app.services.inbound import InboundProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])

# Shared processor instance
_classifier = ClassifierEngine()
_processor = InboundProcessor(_classifier)


def _validate_twilio_request(request: Request, form_data: str) -> bool:
    """Validate that the request genuinely came from Twilio."""
    if not settings.twilio_auth_token:
        logger.warning("Twilio auth token not set — skipping validation.")
        return True  # Allow in dev mode
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(
        str(request.url),
        form_data,
        request.headers.get("X-Twilio-Signature", ""),
    )


@router.post("/sms")
async def inbound_sms(request: Request) -> Response:
    """
    Handle inbound SMS from Twilio.

    Twilio POSTs form-encoded data with:
      - From: sender's phone number (E.164)
      - Body: message text
      - MessageSid: unique message ID
      - To: our Twilio number
      - (and more)
    """
    body = await request.body()
    form_str = body.decode("utf-8")
    form_data = parse_qs(form_str)

    # Validate Twilio signature
    if not _validate_twilio_request(request, form_str):
        logger.warning("Invalid Twilio signature — rejecting.")
        return Response("Invalid signature", status_code=403)

    sender = form_data.get("From", [""])[0]
    message_text = form_data.get("Body", [""])[0]
    message_sid = form_data.get("MessageSid", [""])[0]

    logger.info("Inbound SMS: from=%s body=%s", sender, message_text[:200])

    raw_payload = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}

    async with async_session() as session:
        result = await _processor.process(
            session=session,
            channel="sms",
            sender_id=sender,
            raw_text=message_text,
            raw_payload=raw_payload,
        )

    logger.info("Processed inbound SMS: %s", result)

    # Return TwiML response (empty = no reply needed)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


@router.post("/voice")
async def inbound_voice(request: Request) -> Response:
    """
    Handle inbound voice calls from Twilio.

    For MVP: play a short prompt and record a voicemail.
    The recording webhook (/webhooks/twilio/recording) handles the result.
    """
    # Return TwiML that prompts for a voicemail
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Say voice='alice'>You've reached the TLG Homes job site status line. "
        "Please leave a message after the beep describing your issue and which house you're at. "
        "Speak clearly and include the address.</Say>"
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

    Twilio POSTs with RecordingUrl, From, etc.
    For MVP: log the recording URL; transcription will be added in Phase 2.
    """
    body = await request.body()
    form_str = body.decode("utf-8")
    form_data = parse_qs(form_str)

    recording_url = form_data.get("RecordingUrl", [""])[0]
    sender = form_data.get("From", [""])[0]
    duration = form_data.get("RecordingDuration", ["0"])[0]

    logger.info(
        "Voice recording: from=%s url=%s duration=%ss",
        sender, recording_url, duration,
    )

    raw_payload = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}

    async with async_session() as session:
        result = await _processor.process(
            session=session,
            channel="voice_message",
            sender_id=sender,
            raw_text=f"[Voice recording — duration: {duration}s, url: {recording_url}]",
            audio_url=recording_url,
            raw_payload=raw_payload,
        )

    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )
