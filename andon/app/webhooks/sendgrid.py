"""
SendGrid Inbound Parse webhook handler.

Receives emails sent to a dedicated address (e.g. issues@yourdomain.com)
and routes them through the standard InboundProcessor pipeline.

SendGrid configuration:
  1. Add MX record for your inbound subdomain pointing to mx.sendgrid.net
  2. In SendGrid Dashboard → Settings → Inbound Parse:
     - Set the destination URL to https://yourdomain.com/webhooks/sendgrid/inbound
     - Select "Post the raw, full MIME message" (or let SendGrid parse it)

Webhook format (POST multipart/form-data):
  - from:       Sender email address
  - to:         Recipient email address
  - subject:    Email subject line
  - text:       Plain text body
  - html:       HTML body (if present)
  - attachments: Number of attachments (0 if none)
  - attachment-info: JSON metadata for attachments
  - headers:    Raw email headers
  - envelope:   JSON envelope with sending details
"""

import json
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, Response, Form
from typing import Optional

from app.database import async_session
from app.services.classifier import ClassifierEngine
from app.services.inbound import InboundProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/sendgrid", tags=["sendgrid"])

# Shared processor instance (same as used by Twilio webhooks)
_classifier = ClassifierEngine()
_processor = InboundProcessor(_classifier)


@router.post("/inbound")
async def inbound_email(request: Request) -> Response:
    """
    Handle inbound email from SendGrid Inbound Parse.

    SendGrid POSTs form-encoded or multipart data with the parsed email.
    We extract the sender, subject, body, and attachment metadata, then
    pass everything through the standard InboundProcessor pipeline.
    """
    # Read the raw body
    body = await request.body()
    content_type = request.headers.get("content-type", "")

    # Parse form data (SendGrid sends multipart/form-data or application/x-www-form-urlencoded)
    form_data = {}
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            form_data = {k: v for k, v in form.items()}
        else:
            raw_str = body.decode("utf-8", errors="replace")
            parsed = parse_qs(raw_str)
            form_data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except Exception as exc:
        logger.warning("Failed to parse SendGrid payload: %s", exc)
        return Response("Bad request", status_code=400)

    # ── Extract sender email ──
    sender_email = (
        form_data.get("from", "") or
        form_data.get("from_email", "") or
        ""
    ).strip().lower()

    if not sender_email:
        logger.warning("SendGrid webhook received without 'from' field")
        return Response("Missing sender", status_code=200)  # 200 so SendGrid doesn't retry

    # ── Extract subject + body ──
    subject = (form_data.get("subject", "") or "").strip()
    body_text = (form_data.get("text", "") or "").strip()
    body_html = (form_data.get("html", "") or "").strip()

    # Combine subject + body for classification
    full_text = f"{subject}\n\n{body_text}" if subject else body_text
    if not full_text:
        full_text = body_html or "(no text content)"

    # ── Extract attachment metadata ──
    attachments_count = int(form_data.get("attachments", 0) or 0)
    attachment_info_raw = form_data.get("attachment-info", "{}")
    attachment_metadata = []
    try:
        attachment_meta = json.loads(attachment_info_raw) if isinstance(attachment_info_raw, str) else {}
        for key, meta in attachment_meta.items():
            attachment_metadata.append({
                "filename": meta.get("filename", f"attachment_{key}"),
                "type": meta.get("type", "unknown"),
                "size": meta.get("size", 0),
            })
    except (json.JSONDecodeError, TypeError):
        pass

    logger.info(
        "Inbound email: from=%s subject=%s attachments=%d",
        sender_email, subject[:80], attachments_count,
    )

    # ── Build raw payload for the events table ──
    raw_payload = {
        "from": sender_email,
        "subject": subject,
        "attachments": attachments_count,
        "attachment_metadata": attachment_metadata,
        "envelope": form_data.get("envelope", ""),
        "headers": form_data.get("headers", "")[:500],
    }

    # ── Process through InboundProcessor ──
    async with async_session() as session:
        result = await _processor.process(
            session=session,
            channel="email",
            sender_id=sender_email,
            raw_text=full_text,
            raw_payload=raw_payload,
        )

    logger.info("Processed inbound email: %s", result)

    # Return 200 OK to acknowledge receipt (SendGrid retries on non-200)
    return Response("OK", status_code=200)
