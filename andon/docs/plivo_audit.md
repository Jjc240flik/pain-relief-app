# Plivo Implementation Audit — Sprint Zero

**Date:** July 21, 2026
**Status:** Audit Complete — No Code Changes Yet

---

## 1. Current Status by Channel

| Channel | Route | Status | Details |
|---|---|---|---|
| **SMS Inbound** | `POST /webhooks/plivo/sms` | ⚠️ Route exists, handles Plivo format | No signature validation. No dedup. No async processing (blocks in webhook). Tested working with curl. |
| **SMS Outbound** | `OutboundService.send_sms()` | ⚠️ Plivo provider branch exists | PLIVO_AUTH_ID/TOKEN are empty — falls back to log mode. Cannot send real SMS. |
| **MMS Inbound** | `POST /webhooks/plivo/sms` | ⚠️ Parses Media field, extracts URLs | Media URLs stored as `plivo_url` — not downloaded to local/S3 storage. |
| **MMS Outbound** | — | ❌ Not implemented | No Plivo equivalent exists. MVP may not require it. |
| **Voice Inbound** | `POST /webhooks/plivo/voice` | ✅ Responds with Plivo XML | Prompt plays, recording starts. |
| **Voice Recording** | `POST /webhooks/plivo/recording` | ⚠️ Receives callback, stores URL | Transcription requires OPENAI_API_KEY (empty). Audio not downloaded. |
| **Delivery Status** | — | ❌ Not implemented | No Plivo delivery callback route exists. |
| **Signature Validation** | — | ❌ Missing | Plivo webhook accepts unauthenticated POST requests. |
| **Duplicate Protection** | — | ❌ Missing | MessageUUID is extracted but never checked against stored messages. |

---

## 2. Implementation Gaps

### Critical (Blocks Pilot)

| # | Gap | File | Impact |
|---|---|---|---|
| 1 | **PLIVO_AUTH_ID is empty** | `.env` | All outbound SMS falls back to log mode. No real messages sent. |
| 2 | **PLIVO_AUTH_TOKEN is empty** | `.env` | Same as above. |
| 3 | **PLIVO_PHONE_NUMBER is empty** | `.env` | Outbound SMS has no source number. |
| 4 | **OPENAI_API_KEY is empty** | `.env` | Voice transcription silently fails. All voicemails become `[Voice recording — pending]`. |
| 5 | **No signature validation** | `webhooks/plivo.py` | Anyone can POST to `/_plivo/sms` and create fake cards. |
| 6 | **No duplicate protection** | `webhooks/plivo.py` | Same message delivered twice creates duplicate cards. |

### Important (Should Fix Before Pilot)

| # | Gap | File | Impact |
|---|---|---|---|
| 7 | **Webhook blocks during processing** | `webhooks/plivo.py` | Classification, event creation, and card creation happen inside the POST handler. Plivo may timeout on slow classification. |
| 8 | **Media URLs not downloaded** | `webhooks/plivo.py` | Plivo media URLs expire. Photos will break after 24h. |
| 9 | **No delivery status tracking** | — | Cannot confirm whether outbound SMS was delivered. |
| 10 | **Route is `/sms` not `/message`** | `webhooks/plivo.py` | Plivo console expects `/message` by convention. Works either way but differs from TECH_SPEC. |

### Minor (Defer)

| # | Gap | File | Impact |
|---|---|---|---|
| 11 | **Twilio code still active** | `webhooks/twilio.py` | Dead code. Not used if Plivo is configured. Safe to leave. |
| 12 | **Hardcoded "TLG –" in messages** | `services/outbound.py` | Outbound SMS prefix is hardcoded. Low priority for pilot. |
| 13 | **No MMS outbound** | — | Not required for MVP pilot. Photos are inbound only. |
| 14 | **Transcriber references Twilio auth** | `services/transcriber.py` | Minor — works for any HTTP URL. |

---

## 3. Plivo Console Configuration Required

These are actions you must complete in the Plivo dashboard:

### Account Setup
1. Sign up at https://console.plivo.com
2. Purchase a phone number with **SMS, MMS, and Voice** capabilities
3. Copy `Auth ID` and `Auth Token` from the console

### Phone Number Configuration
4. Set the **Message URL** to:
   ```
   POST http://72.61.108.184:8000/webhooks/plivo/sms
   ```
5. Set the **Voice URL** to:
   ```
   POST http://72.61.108.184:8000/webhooks/plivo/voice
   ```
6. Set the **Recording callback URL** to:
   ```
   POST http://72.61.108.184:8000/webhooks/plivo/recording
   ```
7. *(Optional)* Set the **Delivery callback URL** to:
   ```
   POST http://72.61.108.184:8000/webhooks/plivo/delivery
   ```

### OpenAI Setup (for Voice Transcription)
8. Get an OpenAI API key from https://platform.openai.com/api-keys
9. Add it to `.env`

---

## 4. Environment Variables Required

| Variable | Current | Required For | Status |
|---|---|---|---|
| `PLIVO_AUTH_ID` | Empty | Outbound SMS/MMS | ❌ **You must provide** |
| `PLIVO_AUTH_TOKEN` | Empty | Outbound SMS/MMS | ❌ **You must provide** |
| `PLIVO_PHONE_NUMBER` | Empty | Outbound SMS source number | ❌ **You must provide** |
| `OPENAI_API_KEY` | Empty | Voice transcription via Whisper | ❌ **You must provide** |
| `TWILIO_ACCOUNT_SID` | Set | Fallback (can disable) | ✅ Has value |
| `TWILIO_AUTH_TOKEN` | Set | Fallback | ✅ Has value |
| `TWILIO_PHONE_NUMBER` | Set | Fallback | ✅ Has value |
| `MEDIA_DIR` | `media` | Photo/video storage | ✅ Default works |

---

## 5. Code Changes Required

### Before Plivo can send/receive real messages (0 code changes — purely config)

1. **You provide Plivo credentials** → fill in `.env`

### After credentials are set, these code changes are needed:

| # | Change | File | Effort | Priority |
|---|---|---|---|---|
| 1 | Add Plivo signature validation | `webhooks/plivo.py` | 1 hour | High |
| 2 | Add MessageUUID dedup check | `webhooks/plivo.py` | 30 min | High |
| 3 | Download media to local/S3 storage | `webhooks/plivo.py` + `media_store.py` | 1 hour | Medium |
| 4 | Add delivery status callback route | `webhooks/plivo.py` | 30 min | Medium |
| 5 | Add async queue pattern (store → return 200 → process) | `webhooks/plivo.py` + background worker | 2 hours | Medium |
| 6 | Validate webhook payload completeness | `webhooks/plivo.py` | 30 min | Low |

---

## 6. Working Software Test Results

| Test | Date | Result |
|---|---|---|
| Plivo SMS webhook responds 200 | Jul 21 | ✅ PASS |
| Plivo Voice webhook responds 200 | Jul 21 | ✅ PASS |
| Inbound SMS → event created | Jul 21 | ✅ PASS |
| Inbound SMS → card created | Jul 21 | ✅ PASS |
| Keyword classifier runs | Jul 21 | ✅ PASS |
| Outbound (log mode) | Jul 21 | ✅ PASS (dev log) |
| Voice transcription | — | ❌ BLOCKED (OPENAI_API_KEY) |
| Real Plivo SMS send | — | ❌ BLOCKED (plivo creds) |
| Real Plivo MMS send | — | ❌ BLOCKED (plivo creds) |

---

## 7. Estimated Effort

| Phase | Work | Time |
|---|---|---|
| **Config** | You provide Plivo credentials + OpenAI key | 15 min (your time) |
| **Config** | Plivo console: set webhook URLs | 10 min (your time) |
| **Sprint** | Code: signature validation + dedup + media download | 2-3 hours |
| **Sprint** | Code: delivery callback + async queue | 2-3 hours |
| **Testing** | End-to-end SMS/MMS/Voice | 1-2 hours |

**Total code effort: 4-6 hours** after credentials are provided.

---

## 8. Recommended First Step

**You provide the missing credentials.**

Without these three values, no code change will make Plivo functional:

```bash
# In /root/pain-relief-app/andon/.env
PLIVO_AUTH_ID=your_auth_id_from_plivo_console
PLIVO_AUTH_TOKEN=your_auth_token_from_plivo_console
PLIVO_PHONE_NUMBER=+1XXXXXXXXXX
OPENAI_API_KEY=sk-your_openai_key
```

Once those are in place, I can:
1. Add signature validation (15 min)
2. Add dedup (15 min)
3. Add outbound MMS support if needed (30 min)
4. Add delivery callback (30 min)
5. Download media to local storage (1 hour)
6. Verify end-to-end SMS/MMS/Voice

**SMS could be working within 1 hour** of credentials being set.
