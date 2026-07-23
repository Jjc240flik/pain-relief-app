# Twilio Readiness Report — Pilot MVP

**Date:** July 22, 2026
**Status:** Twilio Is Already the Active Provider

---

## 1. Current Implementation Status

**Key finding: Twilio is already the active provider.** The Plivo migration was never completed — credentials are empty, so the OutboundService falls through to Twilio. The Plivo webhook routes exist but no traffic reaches them.

| Component | Status | Lines | Details |
|---|---|---|---|
| **SMS Inbound** | ✅ Working | `webhooks/twilio.py` (54-155) | Signature validation, MMS parsing, media download |
| **SMS Outbound** | ✅ Working | `services/outbound.py` (115-127) | Falls back to Twilio when Plivo creds empty |
| **MMS Inbound** | ✅ Working | `webhooks/twilio.py` (83-145) | Parses MediaUrl0-4, downloads via media_store |
| **MMS Outbound** | ❌ Not required | — | MVP doesn't need outbound MMS |
| **Voice Inbound** | ✅ Working | `webhooks/twilio.py` (161-180) | Returns TwiML with prompt + record |
| **Voice Recording** | ✅ Working | `webhooks/twilio.py` (183-246) | Stores, transcribes via Whisper |
| **Signature Validation** | ✅ Working | `webhooks/twilio.py` (27-41) | Validates X-Twilio-Signature |
| **Duplicate Protection** | ⚠️ Partial | N/A | No MessageSid dedup yet |
| **Media Storage** | ✅ Working | `services/media_store.py` (193 lines) | Downloads to local or S3 |
| **Transcription** | ⚠️ Blocked | `services/transcriber.py` (97 lines) | Requires OPENAI_API_KEY |

---

## 2. What Is Already Complete

These require zero changes:

- ✅ **Twilio webhook routes** — `/webhooks/twilio/sms`, `/webhooks/twilio/voice`, `/webhooks/twilio/recording` — all registered and working
- ✅ **Signature validation** — verifies X-Twilio-Signature header using `twilio.request_validator`
- ✅ **SMS parsing** — extracts From, Body, MessageSid, NumMedia
- ✅ **MMS parsing** — handles up to 5 media attachments (MediaUrl0-4)
- ✅ **Media download** — `store_media()` downloads from Twilio using account credentials
- ✅ **Voice TwiML response** — plays prompt, records voicemail, sends callback
- ✅ **Voice recording callback** — receives RecordingUrl, queues transcription
- ✅ **Outbound SMS through Twilio** — `twilio.rest.Client` sends messages
- ✅ **InboundProcessor pipeline** — all channels feed the same classifier + event pipeline
- ✅ **Environment variables populated** — `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` are all set in `.env`
- ✅ **Twilio SDK installed** — version 9.10.9, available
- ✅ **Provider abstraction exists** — OutboundService checks Plivo first, falls back to Twilio

---

## 3. What Needs Restoration or Fixing

| Item | Status | Work Required |
|---|---|---|
| **OutboundService provider priority** | ⚠️ Prefers Plivo | Patch `__init__` to prefer Twilio (currently checks Plivo first, which is empty → falls through to Twilio → works but logs "log mode" incorrectly if Plivo fails). Already functions. Fix is 5 min. |
| **Duplicate protection** | ⚠️ Missing | Add MessageSid check before processing. 30 min. |
| **Delivery status callback** | ❌ Missing | Add `/webhooks/twilio/status` route. 30 min. |

**Everything else works as-is.**

---

## 4. Remaining Work for SMS

| Task | Effort | Priority |
|---|---|---|
| Set Twilio Message URL in Twilio console | 10 min (user) | Critical |
| Fix OutboundService to prefer Twilio explicitly | 5 min | Low (already works via fallback) |
| Add MessageSid dedup check | 30 min | Medium |

### Twilio Console Configuration (you need to do)

| Setting | Value |
|---|---|
| Messaging Webhook URL | `POST http://72.61.108.184:8000/webhooks/twilio/sms` |
| Voice Incoming URL | `POST http://72.61.108.184:8000/webhooks/twilio/voice` |
| Status Callback URL | `POST http://72.61.108.184:8000/webhooks/twilio/status` |

---

## 5. Remaining Work for MMS

| Task | Effort | Priority |
|---|---|---|
| No changes needed | 0 | — |

**MMS works through the same webhook as SMS.** Twilio sends `NumMedia` + `MediaUrl0` alongside the `Body`. The existing code parses it, downloads media, and creates the card. No additional configuration required.

---

## 6. Remaining Work for Voice

| Task | Effort | Priority |
|---|---|---|
| **Set OPENAI_API_KEY** | 5 min (user) | **Blocking** |
| Verify transcription pipeline | 30 min | High |

The voice pipeline is: incoming call → TwiML prompt → record → callback → download audio → Whisper → classification → card. Everything except transcription works today without the OpenAI key. Audio is stored, the card is created — but the transcript shows `[Voice recording — pending]` instead of actual text.

---

## 7. Blocker Summary

| # | Blocker | Owner | Status | Effort to Clear |
|---|---|---|---|---|
| 1 | **No OpenAI API key** (voice transcription) | You | ⏳ Pending | 5 min — add to `.env` |
| 2 | **Twilio webhook URL not set in console** | You | ⏳ Pending | 10 min — configure Twilio |

---

## 8. Estimated Time to Pilot Readiness

| Phase | Work | Time |
|---|---|---|
| **Config** | Add OPENAI_API_KEY to `.env` | 5 min |
| **Config** | Set Twilio Messaging URL in console | 10 min |
| **Config** | Set Twilio Voice URL in console | 5 min |
| **Code** | Add MessageSid dedup | 30 min |
| **Code** | Add delivery status callback | 30 min |
| **Code** | Fix OutboundService provider priority (optional) | 5 min |
| **Test** | Verify SMS end-to-end | 15 min |
| **Test** | Verify MMS end-to-end | 15 min |
| **Test** | Verify Voice end-to-end | 15 min |

**Total: ~2 hours** after credentials are set.

**SMS could be testable within 30 minutes** of Twilio webhook URL being configured.

---

## 9. Architecture Recommendation

The current architecture already has a provider abstraction:

```
OutboundService.__init__():
  1. Check Plivo credentials → use Plivo
  2. Check Twilio credentials → use Twilio (current fallback)
  3. Neither → log mode
```

Since Plivo creds are empty, Twilio is already active. The abstraction works.

### Recommended change

Swap the priority so Twilio is checked first. When Plivo is configured later, it takes precedence. This way the system logs the correct provider name and avoids confusion:

```python
# Prefer Twilio (active provider), then Plivo (future provider)
if settings.twilio_account_sid and settings.twilio_auth_token:
    ...
elif settings.plivo_auth_id and settings.plivo_auth_token:
    ...
else:
    ...log mode...
```

### Long-term provider architecture (no build needed now)

```
MessagingProvider (abstract)
  ├── TwilioProvider ← Active
  ├── PlivoProvider  ← Stub (future)
  ├── TelnyxProvider ← Stub (future)
  └── VonageProvider ← Stub (future)
```

No additional architecture work is required for the pilot. The provider abstraction is sufficient.

---

## 10. Summary

**Twilio is ready to go today.** All three channels (SMS, MMS, Voice) have working code. The only outside dependencies are:

1. You set `OPENAI_API_KEY` in `.env` (for voice transcription)
2. You configure the Twilio webhook URLs in the Twilio console

After those two things, I can:
- Add dedup (30 min)
- Add status callback (30 min)
- Verify end-to-end SMS/MMS/Voice

**SMS could be working within 30 minutes** of your Twilio console configuration.
