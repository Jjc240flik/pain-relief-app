# Technical Specification & Architecture — SMS Andon System (MVP)

> **Author:** Hermes (Principal Software Engineer)
> **PRD:** `/root/pain-relief-app/PRD.md`
> **Target:** Buildable by a small team in 3–4 weeks

---

## 1. Recommended Technology Stack

### Backend Framework: FastAPI (Python 3.11+)
**Why:** Async-native, excellent webhook handling (Twilio/SendGrid both POST to endpoints), auto-generated OpenAPI docs, Pydantic validation baked in. Django would add ORM overhead and synchronous baggage for what is fundamentally a webhook + scheduler app. Flask is too barebones for clean project structure without bolting on extensions. FastAPI hits the sweet spot for a 3–4 week MVP.

**Trade-off:** FastAPI is less opinionated than Django — we own the project structure. This is a net positive for a focused app.

### Database: PostgreSQL 15+
**Why:** Reliable, mature, JSONB for the Events table (variable-structured audit entries), excellent async driver support (asyncpg), built-in cron scheduling with pg_cron if needed later. SQLite is out — we need concurrent writes from webhooks. MySQL would work but Postgres JSONB and array types are genuinely useful here.

**ORM:** SQLAlchemy 2.0 (async) with Alembic for migrations. SQLAlchemy 2.0's new-style queries are clean, and Alembic gives us safe schema evolution from day one.

### SMS + Voice: Twilio
**Why:** Dual SMS and voice under one API. Inbound SMS lands as an HTTP POST webhook. Voice calls route to Twilio Studio Flow or TwiML for voicemail recording with transcription (Twilio's built-in transcription is passable; we can swap to Deepgram later if quality needs improve). No competitor offers the same breadth with the same integration simplicity for MVP.

**Trade-off:** Twilio's per-message pricing is higher than some competitors (e.g., AWS SNS for SMS only). The convenience of unified SMS+Voice+transcription for MVP justifies the cost. We can optimize channels later.

### Email: SendGrid Inbound Parse
**Why:** Forward inbound emails as an HTTP POST with parsed subject/body/attachments. Free tier handles 100 emails/day, which is ample for a builder with 10–15 active houses. AWS SES is cheaper at scale but requires DNS verification and has more moving parts for inbound parsing (SNS + S3 + Lambda). SendGrid Inbound Parse is a single webhook URL — 15 minutes to wire up.

**Trade-off:** Vendor lock-in on inbound email parsing. The standard is simple enough that switching to SES later costs about 2 days of work.

### Transcription: OpenAI Whisper API
**Why:** Best quality-per-dollar for short-form voicemail and voice notes. No infrastructure to manage. The `whisper-1` model handles <25 MB audio files, which covers any voicemail. Deepgram is a reasonable alternative with real-time streaming (not needed for MVP), but Whisper's accuracy on construction jargon (tested informally) edges it out.

**Trade-off:** Per-minute cost. A 30-second voicemail costs ~$0.002. At 5 voicemails/day that's ~$0.30/month — negligible. If volume grows 100x, we'd evaluate Deepgram or local Whisper.

### Frontend / Dashboard: Jinja2 Templates + HTMX + Alpine.js + Tailwind CSS
**Why:** The Daily View is one page with rows and action buttons. HTMX lets us add "one-tap actions" with zero JavaScript build pipeline. Alpine.js handles lightweight client state (modals, date pickers). Jinja2 templates render on the server so the dashboard is part of the same FastAPI deployment — no CORS, no API auth to build, no two-repo complexity.

**Trade-off:** Not suitable for a complex SPA. The Daily View IS the MVP frontend. If we add more complex views later, we can serve a React SPA from the same backend under `/app/`. For now, this is the fastest path to a working UI.

### Background Scheduling: APScheduler
**Why:** Runs in-process with FastAPI. Handles cron-style scheduling (daily readiness checks, day-before confirmations) and interval scheduling (midpoint checks during framing/concrete windows). No Redis, no Celery, no separate worker process for MVP. Uses the existing PostgreSQL connection for job coordination.

**Trade-off:** No retry queue, no persistent message broker. If a scheduled job fails, APScheduler retries per configuration. For MVP scale (10–15 houses, <100 messages/day), this is sufficient. If the app grows, we introduce Celery + Redis for background processing — a well-understood migration path.

### Summary Table

| Layer | Choice | Alternative Considered | Why This Wins |
|---|---|---|---|
| Backend | FastAPI | Django, Flask | Async-native, webhook-optimized |
| Database | PostgreSQL | MySQL, SQLite | JSONB, async support, maturity |
| ORM | SQLAlchemy 2.0 async | Django ORM, raw SQL | Migration support, type safety |
| SMS/Voice | Twilio | AWS SNS, Vonage | Unified SMS+Voice+Transcription |
| Email inbound | SendGrid Inbound Parse | AWS SES | Single webhook, 15-min setup |
| Transcription | OpenAI Whisper API | Deepgram, AssemblyAI | Best quality/dollar, zero infra |
| Dashboard | Jinja2 + HTMX + Tailwind | React, Streamlit | No build pipeline, same deployment |
| Scheduler | APScheduler | Celery + Redis | No extra infra for MVP |

---

## 2. Database Schema

### ERD (Text)
```
houses 1──N schedule_items
houses 1──N events
schedule_items 1──N events
contacts N──M schedule_items  (via assigned_phone)
```

### Table: `houses`

```sql
CREATE TABLE houses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address       TEXT NOT NULL,
    city          TEXT,
    state         TEXT DEFAULT 'WI',
    current_phase INTEGER,  -- 1-10, NULL until construction starts
    overall_status CHAR(1) NOT NULL DEFAULT 'G' CHECK (overall_status IN ('R','Y','G')),
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_houses_status ON houses (overall_status) WHERE overall_status IN ('R','Y');
CREATE INDEX idx_houses_phase ON houses (current_phase);
```

**Why UUID:** Protects against enumeration attacks if IDs leak in URLs. Performance cost is negligible at this scale.

### Table: `schedule_items`

```sql
CREATE TYPE trade_phase AS ENUM (
    'foundation_concrete', 'framing', 'plumbing_rough', 'hvac_rough',
    'electrical_rough', 'drywall_plaster', 'paint', 'flooring',
    'cabinets', 'finish_work'
);

CREATE TYPE schedule_status AS ENUM ('scheduled', 'in_progress', 'complete');

CREATE TABLE schedule_items (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    house_id           UUID NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    trade              trade_phase NOT NULL,
    scheduled_start    DATE NOT NULL,
    scheduled_end      DATE,
    assigned_phone     TEXT,  -- E.164 format
    status             schedule_status NOT NULL DEFAULT 'scheduled',
    andon_status       CHAR(1) DEFAULT 'G' CHECK (andon_status IN ('R','Y','G')),
    last_touch_ts      TIMESTAMPTZ,
    cleanup_confirmed  BOOLEAN DEFAULT FALSE,
    readiness_lead_days INTEGER NOT NULL DEFAULT 7,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sched_house ON schedule_items (house_id, trade);
CREATE INDEX idx_sched_andon ON schedule_items (andon_status) WHERE andon_status IN ('R','Y');
CREATE INDEX idx_sched_dates ON schedule_items (scheduled_start);
```

**Why enum for trade_phase:** The PRD explicitly defines exactly 10 phases. An enum prevents invalid values and makes the schema self-documenting. If new phases are needed later, ALTER TYPE ADD VALUE is online-safe in PostgreSQL 15+.

### Table: `contacts`

```sql
CREATE TABLE contacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade       trade_phase,
    name        TEXT NOT NULL,
    company     TEXT,
    phone       TEXT,  -- E.164
    email       TEXT,
    notes       TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contacts_phone ON contacts (phone);
CREATE INDEX idx_contacts_trade ON contacts (trade);
```

**Note:** `trade` is nullable because a contact might be a designer or owner who isn't tied to a single phase.

### Table: `events` (Immutable Audit Log)

```sql
CREATE TYPE channel_type AS ENUM ('sms', 'email', 'phone_call', 'voice_message');
CREATE TYPE direction_type AS ENUM ('inbound', 'outbound');
CREATE TYPE triggered_by_type AS ENUM ('pm', 'foreman', 'sub', 'system');

CREATE TABLE events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp         TIMESTAMPTZ NOT NULL DEFAULT now(),
    house_id          UUID REFERENCES houses(id),
    schedule_item_id  UUID REFERENCES schedule_items(id),
    trade             trade_phase,
    direction         direction_type NOT NULL,
    channel           channel_type NOT NULL,
    full_text         TEXT,
    original_media_url TEXT,  -- S3/file path for voice recordings
    outcome           CHAR(1) CHECK (outcome IN ('R','Y','G')),
    triggered_by      triggered_by_type NOT NULL,
    confidence_score  REAL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    sender_phone      TEXT,
    sender_email      TEXT,
    raw_payload       JSONB   -- full webhook body for debugging
);

-- Partition by month for query performance at scale
CREATE INDEX idx_events_ts ON events (timestamp DESC);
CREATE INDEX idx_events_house ON events (house_id, timestamp DESC);
CREATE INDEX idx_events_direction ON events (direction, channel);
```

**Why immutable:** Events are INSERT-only. No UPDATE, no DELETE. This is the system of record. If a status change was wrong, we INSERT a corrective event — never modify history. This gives us a full trace for debugging disputes.

**Why JSONB raw_payload:** When debugging integration issues (e.g., Twilio format changes), having the original webhook body is invaluable. Storage cost is negligible.

### Table: `designer_forwarding_log`

```sql
CREATE TABLE designer_forwarding_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id    UUID NOT NULL REFERENCES events(id),
    house_id    UUID NOT NULL REFERENCES houses(id),
    question    TEXT NOT NULL,
    answer      TEXT,
    designer_contact_id UUID REFERENCES contacts(id),
    forwarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    answered_at TIMESTAMPTZ,
    fallback_to_pm BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_designer_house ON designer_forwarding_log (house_id, forwarded_at DESC);
```

---

## 3. System Architecture Overview

### Text Flow Diagram

```
                         ┌──────────────────────────┐
                         │     External Channels     │
                         │                          │
  SMS ────Twilio─────────┤  ┌──────────────────┐    │
  Call ───Twilio─────────┤  │  Inbound Webhooks │    │
  Email ──SendGrid───────┤  └────────┬─────────┘    │
  Voice ──Twilio─────────┘           │              │
                         ┌───────────┴───────────┐  │
                         │   FastAPI Application  │  │
                         │    (same process)      │  │
                         │                        │  │
  ┌──────────────────────┼─ Router Layer ────────┼──┤
  │                      │  /webhooks/twilio      │  │
  │   APScheduler        │  /webhooks/sendgrid    │  │
  │   (in-process)       │  /dashboard/*          │  │
  │                      │  /api/schedule/*       │  │
  │   - Readiness checks │                        │  │
  │   - Day-before confs └───────────┬────────────┘  │
  │   - Completion checks           │               │
  │   - Midpoint checks   ┌─────────┴────────────┐  │
  └──────────┬────────────┤   Service Layer       │  │
             │            │                       │  │
             │            │  InboundProcessor     │  │
             │            │  OutboundService      │  │
             │            │  ClassifierEngine     │  │
             │            │  ScheduleService      │  │
             │            │  DashboardView        │  │
             │            └─────────┬────────────┘  │
             │                      │               │
             └──────────────────────┼───────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │     PostgreSQL       │
                         │                      │
                         │  houses              │
                         │  schedule_items      │
                         │  contacts            │
                         │  events              │
                         │  designer_forwarding │
                         └─────────────────────┘
```

### Data Flow for an Inbound Message

```
1.  Sub sends "ISSUE water damage" via SMS
        │
2.  Twilio POSTs to /webhooks/twilio/sms
        │
3.  FastAPI validates signature, stores raw_payload
        │
4.  InboundProcessor:
    a. Resolve sender phone → contact → trade
    b. If unknown → log to review queue, return 200 (Twilio needs ACK)
    c. Extract text, detect keywords
        │
5.  ClassifierEngine:
    a. Check for selections keywords → route to designer flow
    b. Check for ISSUE/emergency keywords → classify R/Y
    c. Check structured reply (1/2/3/A/B)
    d. Assign confidence_score
        │
6.  Update schedule_item.andon_status if needed
        │
7.  INSERT immutable event record
        │
8.  Apply side effects:
    a. If Red → notify Jim immediately (break quiet hours)
    b. If selections → forward to designer
    c. If cleanup B=No → set Yellow
        │
9.  Return 200/XML to Twilio
```

---

## 4. Inbound Message Processing Pipeline

### Step-by-step Pseudocode

```
function process_inbound(channel, sender_id, raw_text, audio_url=None):

    # STEP 1: Identify sender
    contact = resolve_sender(sender_id, channel)
    if not contact:
        write_review_queue(sender_id, channel, raw_text)
        return  # Unknown sender — human reviews later

    # STEP 2: Transcribe if voice
    if audio_url:
        transcript = transcribe_audio(audio_url)  # OpenAI Whisper API
        confidence = transcript.confidence  # 0.0–1.0
        full_text = transcript.text
    else:
        full_text = raw_text
        confidence = 1.0

    # STEP 3: Detect house + trade
    #    Try to extract from message text (address mention)
    #    If not found, use sender's most recent active schedule_item
    house, schedule = resolve_context(sender_id, channel, full_text)

    # STEP 4: Classify
    status, severity, selections_flag = classify(full_text)

    # STEP 5: Handle selections special case
    if selections_flag and house:
        forward_to_designer(full_text, house.address)
        # Still log and process normally below

    # STEP 6: Update schedule item status
    if status and schedule:
        schedule.andon_status = status
        schedule.last_touch_ts = now()

        # Post-status side effects
        if status == 'R' and schedule.trade == 'foundation_concrete':
            notify_jim_immediate(house, schedule, full_text)
        elif status == 'R' and schedule.trade == 'framing':
            if is_structural_issue(full_text):
                notify_jim_immediate(house, schedule, full_text)
            else:
                notify_jim_and_clint(house, schedule, full_text)
        elif status == 'R':
            notify_jim(house, schedule, full_text)
            notify_clint(house, schedule, full_text)
        elif status == 'Y':
            notify_jim(house, schedule, full_text)  # Yellow = monitored

    # STEP 7: Log immutably
    INSERT INTO events (
        timestamp, house_id, schedule_item_id, trade,
        direction='inbound', channel, full_text,
        original_media_url=audio_url,
        outcome=status, triggered_by='sub',
        confidence_score=confidence,
        sender_phone=sender_id,
        raw_payload=null  # caller fills this
    )

    # STEP 8: Rate limit tracking
    touch_rate_limit(house.id, schedule.trade)
```

### Classification Engine (V1 — Keyword Rules)

```
function classify(text):
    text_lower = text.lower()

    # Selection keywords — forward to designer
    selection_keywords = [
        'paint', 'color', 'finish', 'selection', 'what color',
        'hardware', 'fixture', 'countertop', 'cabinet color',
        'floor color', 'trim color', 'door style'
    ]
    if any(kw in text_lower for kw in selection_keywords):
        return (None, None, True)  # selections_flag = True

    # Emergency keywords — Red
    red_keywords = [
        'issue', 'emergency', 'broken', 'leak', 'flood', 'fire',
        'structural', 'collapsed', 'damage', 'cannot start',
        'can\'t start', 'not ready', 'won\'t be there',
        'stop work', 'shut down', 'code violation',
        'inspection fail', 'failed inspection'
    ]
    if any(kw in text_lower for kw in red_keywords):
        return ('R', 'high', False)

    # Structured reply parsing
    text_clean = text_lower.strip()
    if text_clean in ('2', '3', 'b'):
        return ('R' if text_clean in ('3',) else 'Y', 'medium', False)

    # Cleanup failure
    if text_clean == 'b':
        return ('Y', 'medium', False)

    # Partial completion
    if text_clean == 'partial' or text_clean == '2':
        return ('Y', 'low', False)

    # Default — no status change
    return (None, None, False)
```

**Why keyword rules and not ML:** The PRD explicitly says "start simple with keyword rules + confidence scoring and improve iteratively." A keyword classifier can be written, tested, and deployed in one afternoon. ML adds data collection, labeling, model deployment, and iteration cycles that don't exist yet. The MVP should have 10–20 keyword rules that catch 80% of issues. Rules are trivially debuggable — when someone complains "why was this classified Red?", we can show the exact keyword match.

### Quiet Hours Enforcement

```
function should_send_outbound(contact_phone, is_emergency=False):
    if is_emergency:
        return True  # Red notifications break quiet hours
    current_hour = datetime.now().hour  # 0-23
    if 7 <= current_hour < 19:
        return True
    return False
```

Implementation: Check quiet hours in `OutboundService.send_sms()` BEFORE enqueueing. Emergency notifications (triggered by sub's Red classification) pass `is_emergency=True`.

### Rate Limiting

```
# Data structure: dict keyed by (house_id, trade, date)
# Stored in PostgreSQL for persistence:
CREATE TABLE rate_limit_tracker (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    house_id    UUID NOT NULL REFERENCES houses(id),
    trade       trade_phase NOT NULL,
    date        DATE NOT NULL,
    count       INTEGER NOT NULL DEFAULT 1,
    last_issue  BOOLEAN DEFAULT FALSE,
    UNIQUE(house_id, trade, date)
);

function check_rate_limit(house_id, trade):
    today = date.today()
    row = get_or_create(rate_limit_tracker, house_id, trade, today)
    if row.last_issue:
        return True  # Previous reply was Issue — allow more
    if row.count >= 1:
        return False  # Already sent one auto-text today
    row.count += 1
    return True
```

---

## 5. Core Components & Responsibilities

### 5.1 `InboundProcessor`
**File:** `app/services/inbound.py`

**Responsibility:** Receives all inbound messages from webhook handlers. Orchestrates the pipeline: identify sender → resolve context → transcribe → classify → update → log.

**Key interface:**
```python
class InboundProcessor:
    async def process(
        self,
        channel: ChannelType,
        sender_id: str,
        raw_text: str | None,
        audio_url: str | None,
        raw_payload: dict
    ) -> None:
```

### 5.2 `OutboundService`
**File:** `app/services/outbound.py`

**Responsibility:** Send SMS messages via Twilio. Enforce quiet hours. Handle rate limits. Log every outbound message as an Event.

```python
class OutboundService:
    async def send_sms(
        self,
        to_phone: str,
        body: str,
        house_id: UUID,
        trade: TradePhase,
        is_emergency: bool = False
    ) -> bool:
```

### 5.3 `ClassifierEngine`
**File:** `app/services/classifier.py`

**Responsibility:** Keyword matching, structured reply parsing, confidence scoring. Returns a `ClassificationResult` named tuple.

```python
@dataclass
class ClassificationResult:
    andon_status: str | None  # 'R', 'Y', or None
    confidence: float
    is_selections_query: bool
    matched_keyword: str | None

class ClassifierEngine:
    def classify(self, text: str) -> ClassificationResult:
```

### 5.4 `ScheduleService`
**File:** `app/services/schedule.py`

**Responsibility:** CRUD for schedule_items, status transitions, date adjustments, cascading notifications (push + notify next sub).

### 5.5 `Scheduler` (APScheduler Integration)
**File:** `app/services/scheduler.py`

**Responsibility:** Register and manage recurring jobs:
- Daily `run_readiness_checks()` — checks if any trades are within their readiness window
- Daily `run_day_before_confirmations()` — sends day-before texts
- Daily `run_completion_checks()` — sends completion texts for in-progress items
- Midpoint checks for foundation/concrete and framing

### 5.6 `DashboardView`
**File:** `app/views/dashboard.py`

**Responsibility:** Server-rendered Jinja2 templates for the Daily Red/Yellow view. HTMX endpoints for one-tap actions.

### 5.7 `WebhookHandlers`
**File:** `app/webhooks/twilio.py`, `app/webhooks/sendgrid.py`

**Responsibility:** Validate signatures, parse channel-specific payloads into a normalized format, hand off to `InboundProcessor`. Thin layer — no business logic.

### 5.8 `ContactsService`
**File:** `app/services/contacts.py`

**Responsibility:** Contact lookup by phone/email, import from CSV, review queue for unknown senders.

### 5.9 `DesignerForwarder`
**File:** `app/services/designer.py`

**Responsibility:** Forward selection queries to designer via SMS. Log question + answer. Fallback to Jim.

---

## 6. Key Technical Decisions & Trade-offs

| Decision | Choice | Trade-off |
|---|---|---|
| **Scheduling** | APScheduler in-process vs Celery+Redis | APScheduler adds zero infra but doesn't survive process restart. For MVP, if the server restarts, missed jobs can be detected by the first scheduled check ("did we miss anything?"). Acceptable for <100 msg/day. |
| **Dashboard** | Server-rendered (Jinja2+HTMX) vs SPA | No CORS, no API versioning, no frontend build step. A dev can change the dashboard in one file. The trade-off is that complex interactivity (drag-and-drop rescheduling) is harder in HTMX. MVP doesn't need that. |
| **Transcription** | API call per voicemail vs local Whisper | API calls cost pennies and need zero GPU. For MVP with <10 voicemails/day, this is the right call. We can add local Whisper in a background worker if volume grows. |
| **Classification** | Keyword rules vs NLP model | Rules are transparent and debuggable. A misclassified message shows the exact keyword match instantly. ML models are black boxes that need training data we don't have yet. |
| **Webhook processing** | Synchronous (in request handler) vs queue | For MVP, Twilio's HTTP timeout is 15 seconds. Our pipeline (DB lookup + optional Whisper API call) completes well under that. If we add more expensive processing later, we buffer the webhook body and return 200 immediately, processing async. |
| **Event storage** | Single `events` table vs per-channel tables | Single table with `channel` enum is simpler to query, simpler to monitor. Partitioning by month handles scale. |
| **Contact ID** | Phone-based resolution vs unique ID per sender | Phone is the most reliable identifier for construction subs (they don't change phone numbers often). Email as fallback. Unknown numbers go to a review queue. |

---

## 7. 3-Week Phased Implementation Plan

### Week 1: Foundation — Data Layer + Outbound Engine (Shippable Value: Working SMS confirmations)

**Deliverable:** System sends readiness-check and day-before texts to subs. Events logged. Dashboard shows sent messages.

| Day | Tasks |
|---|---|
| **Mon** | Project scaffold: FastAPI project structure, PostgreSQL setup, Alembic migrations for all 5 tables, Docker Compose for local dev, CI pipeline |
| **Tue** | SQLAlchemy models + repository layer (CRUD for houses, schedule_items, contacts, events). Write unit tests. |
| **Wed** | Contacts import CSV endpoint. `OutboundService` — Twilio integration, quiet hours enforcement, rate limiting. Send a test SMS. |
| **Thu** | `Scheduler` — APScheduler setup: readiness check job, day-before confirmation job. Wire to `OutboundService`. |
| **Fri** | `Events` table full logging for outbound messages. Dashboard basic view: list scheduled messages sent today. Acceptance test: schedule a house, verify SMS is sent at correct interval. |

**Milestone:** Jim can import his houses and contacts, and the system sends automated check-in texts. No inbound processing yet.

### Week 2: Receive — Inbound Pipeline + Classification (Shippable Value: Red/Yellow status reflects sub replies)

**Deliverable:** Subs can reply to SMS. Replies are classified, status updated, Events logged, dashboard shows live Red/Yellow view.

| Day | Tasks |
|---|---|
| **Mon** | `twilio_sms_webhook` — validate signature, parse, hand to `InboundProcessor`. Build `unknown_senders` review queue. Unit tests for phone resolution. |
| **Tue** | `ClassifierEngine` V1 — keyword rules, structured reply parsing (1/2/3/A/B), confidence scoring. Unit tests with construction-specific test cases. |
| **Wed** | Wire classification to schedule status updates. Events logging for inbound. Side effects (notifications for Red/Yellow). Acceptance test: sub texts "2" → status goes Yellow. |
| **Thu** | **Dashboard Daily View** — Jinja2 template, shows Red + Yellow houses only, with trade, last message, time since update, channel icon. One-tap "Resolve" action via HTMX. |
| **Fri** | One-tap "Push +1 day" and "Push +3 days" actions. Schedule change logged in Events. Integration test: full SMS lifecycle (send check-in → sub replies → status updates → dashboard reflects). |

**Milestone:** Complete SMS loop. Jim sees Red/Yellow houses on his dashboard, can resolve or push dates.

### Week 3: Expand — Email, Voice, Completion Checks, Polish (Shippable Value: Multi-channel support + daily completions)

**Deliverable:** All four inbound channels working. Completion/cleanup checks running. Hybrid selections forwarding ready.

| Day | Tasks |
|---|---|
| **Mon** | **Email inbound** — SendGrid Inbound Parse webhook handler. Normalize to InboundProcessor format. Add email channel icon to dashboard. |
| **Tue** | **Voice inbound** — Twilio voicemail TwiML flow. Voicemail received → S3 upload (local disk for MVP) → Whisper API transcription → InboundProcessor pipeline. |
| **Wed** | **Completion + cleanup check** scheduled job. Send completion text, parse response, handle B=No → Yellow. **Midpoint checks** for foundation/concrete and framing. |
| **Thu** | **Hybrid selections forwarding** — detect keywords in any channel, forward to designer via SMS if configured, log to design_forwarding_log. Fallback to Jim. |
| **Fri** | **Polish** — Error handling review, logging pass (structured JSON logs), quiet hours edge cases, rate limit boundary conditions. Documentation: `README.md` with setup instructions, architecture overview diagram. Demo walkthrough. |

**Milestone:** Full MVP as defined in the PRD. Jim can manage 10 houses across all phases with multi-channel sub communication.

---

## 8. Risks, Open Questions & Recommendations

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Twilio phone number provisioning delay** | Medium | High (blocks SMS MVP) | Order Twilio numbers during Week 1 setup. Have a backup SMS provider (e.g., Vonage) identified. |
| **Whisper API latency on voicemails** | Low | Medium | Typical Whisper response is 1–3s for 30s audio. Twilio's webhook timeout is 15s. We're fine, but if latency spikes, move transcription to background task. |
| **Subs reply with unexpected free text** | High | Medium | Classifier returns `confidence < threshold` → log with low confidence, notify Jim as review-needed. Dashboard shows low-confidence entries with a warning icon. |
| **Unknown phone numbers at launch** | High | Low | Write to review queue. Jim manually tags the contact. "Unknown sender" notification on dashboard. |
| **SendGrid inbound email DNS propagation** | Medium | Low | Configure MX records during Week 2. Verify propagation before Week 3 demo. |

### Open Questions for Jim

1. **Designer contact info** — Do you have a phone number for the interior designer(s)? If multiple, how should we pick which one to forward to?
2. **SMS sender name** — Do you want the outbound texts to come from a specific name (e.g., "TLG Homes") or the phone number? Twilio supports Alphanumeric Sender ID for US numbers in some cases.
3. **Review queue** — Who monitors the unknown sender queue? Jim, Clint, or both?
4. **Existing schedule data** — Do you have an existing spreadsheet or system we can import houses and schedules from, or do we start from scratch?
5. **Dashboard access** — Should the dashboard be accessible only from a local network, or do you want web-based auth (simple password or Google OAuth)?

### Recommendations for Post-MVP

1. **Add retry with exponential backoff** for Twilio/SendGrid/Whisper API calls. Implement with `tenacity` library after Week 3.
2. **Structured logging** — Use `structlog` for JSON-formatted logs with request IDs. Easy to add in Week 2.
3. **Health check endpoint** — `GET /health` that pings DB + Twilio API. For operational monitoring.
4. **Don't over-invest in the keyword classifier** — Plan to replace it with a lightweight ML classifier (e.g., scikit-learn logistic regression on TF-IDF features) after you have 500+ labeled events. The keyword rules are a scaffold, not the destination.
5. **One architectural extension to plan for:** If you add more houses (50+), the in-process APScheduler should be promoted to a separate scheduler process or Celery Beat. The code architecture (services layer) stays the same — only the deployment changes.
