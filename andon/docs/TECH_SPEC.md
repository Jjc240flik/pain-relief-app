# Technical Specification & Architecture — TLG Andon MVP

## 1. Scope

This specification updates the original SMS Andon architecture to support:

- Project onboarding
- Flexible schedule maturity
- Estimated, Target, Confirmed, and Actual dates
- Plivo SMS/MMS/Voice intake
- Existing keyword classifier
- AI interpretation for ambiguous input
- Separate Language Grade, Flow Grade, and Final Card Status
- Immutable decision history
- Future Zapier and contractor-platform integrations
- A simple PM-facing dashboard

The core product loop remains:

```text
Receive → Normalize → Interpret → Evaluate Flow → Surface Card → Act → Resolve
```

---

## 2. Recommended Technology Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, Python 3.12 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x async |
| Migrations | Alembic |
| Messaging / Voice | Plivo |
| Email Inbound | SendGrid Inbound Parse or provider-neutral webhook adapter |
| AI Interpretation | OpenAI API with structured JSON output |
| Transcription | OpenAI transcription API |
| Media Storage | S3-compatible object storage |
| Frontend | Jinja2 + HTMX + Tailwind |
| Background Processing | Redis + RQ, Dramatiq, or Celery |
| Scheduler | APScheduler for MVP, separate worker process recommended |
| Keyword Import | OpenPyXL |
| Monitoring | Structured logs + error monitoring + health checks |

### Important Change from the Original Specification

Do not perform AI, transcription, image analysis, or classification synchronously inside the Plivo webhook.

The webhook must:
1. Validate the request
2. Store the raw payload
3. Enqueue a processing job
4. Return HTTP 200 immediately

---

## 3. Logical Agent Architecture

Hermes may use multiple internal agents or services where useful, but responsibilities must remain separate.

### Intake Agent
- Receives SMS, MMS, email, voice, manual, and integration inputs
- Stores raw payload
- Normalizes sender, channel, text, timestamps, and media references

### Context Agent
- Resolves builder, project, trade, contact, and open conversation
- Requests clarification when project context is ambiguous

### Language Agent
- Runs the existing keyword and phrase classifier
- Produces Language Grade
- Determines whether AI interpretation is required

### AI Interpretation Agent
- Extracts structured event data from free-form language
- Does not decide Red, Yellow, or Green

### Project Context Agent
- Loads project schedule maturity, dates, dependencies, contacts, inspections, and current phase

### Flow Engine
- Applies deterministic production-impact rules
- Produces Flow Grade

### Card Generator
- Creates a concise PM-facing card

### Date Engine
- Handles estimated, target, confirmed, and actual dates
- Recommends date changes
- Never silently changes confirmed dates

### Contact Router
- Selects the relevant trade contact, manager, PM, or escalation contact

### Audit Agent
- Stores every stage permanently
- Preserves manager overrides and resolution feedback

These may be implemented as service classes rather than literal autonomous agents.

---

## 4. Data Model

### 4.1 `projects`

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    name TEXT NOT NULL,
    lot_number TEXT,
    street_address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT,
    community TEXT,
    internal_project_number TEXT,
    assigned_pm_contact_id UUID,
    assigned_superintendent_contact_id UUID,
    project_status TEXT NOT NULL DEFAULT 'planning',
    current_phase TEXT,
    current_trade TEXT,
    next_planned_trade TEXT,
    estimated_start DATE,
    target_start DATE,
    actual_start DATE,
    estimated_completion DATE,
    target_completion DATE,
    actual_completion DATE,
    schedule_maturity TEXT NOT NULL DEFAULT 'no_schedule',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Valid `schedule_maturity`:
- `no_schedule`
- `estimated_only`
- `target_schedule`
- `partial_schedule`
- `full_schedule`

### 4.2 `contacts`

```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    name TEXT NOT NULL,
    company_name TEXT,
    trade TEXT,
    role TEXT,
    phone TEXT,
    email TEXT,
    manager_name TEXT,
    manager_phone TEXT,
    preferred_contact_method TEXT,
    is_escalation_contact BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.3 `project_contacts`

```sql
CREATE TABLE project_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    project_role TEXT NOT NULL,
    trade TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_escalation BOOLEAN NOT NULL DEFAULT FALSE,
    assignment_status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, contact_id, project_role, trade)
);
```

### 4.4 `trade_schedule_items`

```sql
CREATE TABLE trade_schedule_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    trade TEXT NOT NULL,
    assigned_contact_id UUID REFERENCES contacts(id),
    estimated_start DATE,
    target_start DATE,
    confirmed_start DATE,
    actual_start DATE,
    estimated_duration_days INTEGER,
    estimated_completion DATE,
    target_completion DATE,
    confirmed_completion DATE,
    actual_completion DATE,
    preceding_trade_item_id UUID REFERENCES trade_schedule_items(id),
    critical_path BOOLEAN NOT NULL DEFAULT FALSE,
    inspection_required BOOLEAN NOT NULL DEFAULT FALSE,
    schedule_status TEXT NOT NULL DEFAULT 'not_scheduled',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.5 `trade_dependencies`

```sql
CREATE TABLE trade_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upstream_item_id UUID NOT NULL REFERENCES trade_schedule_items(id) ON DELETE CASCADE,
    downstream_item_id UUID NOT NULL REFERENCES trade_schedule_items(id) ON DELETE CASCADE,
    dependency_type TEXT NOT NULL DEFAULT 'finish_to_start',
    lag_days INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(upstream_item_id, downstream_item_id)
);
```

### 4.6 `inbound_messages`

```sql
CREATE TABLE inbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID,
    project_id UUID REFERENCES projects(id),
    contact_id UUID REFERENCES contacts(id),
    channel TEXT NOT NULL,
    provider_message_id TEXT,
    sender_identifier TEXT,
    destination_identifier TEXT,
    raw_text TEXT,
    normalized_text TEXT,
    media_urls JSONB,
    raw_payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_status TEXT NOT NULL DEFAULT 'received',
    UNIQUE(channel, provider_message_id)
);
```

### 4.7 `language_grades`

```sql
CREATE TABLE language_grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inbound_message_id UUID NOT NULL REFERENCES inbound_messages(id) ON DELETE CASCADE,
    likely_trade TEXT,
    matched_keywords JSONB NOT NULL DEFAULT '[]',
    matched_phrases JSONB NOT NULL DEFAULT '[]',
    preliminary_severity TEXT NOT NULL,
    confidence_score NUMERIC(5,4),
    ai_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.8 `construction_events`

```sql
CREATE TABLE construction_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inbound_message_id UUID REFERENCES inbound_messages(id),
    project_id UUID REFERENCES projects(id),
    trade_schedule_item_id UUID REFERENCES trade_schedule_items(id),
    event_type TEXT NOT NULL,
    trade TEXT,
    summary TEXT NOT NULL,
    reason TEXT,
    original_date DATE,
    revised_date DATE,
    certainty TEXT NOT NULL,
    structured_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.9 `flow_grades`

```sql
CREATE TABLE flow_grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    construction_event_id UUID NOT NULL REFERENCES construction_events(id) ON DELETE CASCADE,
    schedule_maturity TEXT NOT NULL,
    production_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    affected_trade TEXT,
    affected_inspection TEXT,
    affected_deadline TEXT,
    downstream_impact TEXT,
    time_until_impact_hours INTEGER,
    available_float_hours INTEGER,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    rule_used TEXT NOT NULL,
    confidence_score NUMERIC(5,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.10 `issue_cards`

```sql
CREATE TABLE issue_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    construction_event_id UUID NOT NULL REFERENCES construction_events(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    trade TEXT,
    initial_status TEXT NOT NULL,
    current_status TEXT NOT NULL,
    title TEXT NOT NULL,
    issue_summary TEXT NOT NULL,
    impact_summary TEXT,
    recommended_action TEXT,
    source_channel TEXT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.11 `manager_overrides`

```sql
CREATE TABLE manager_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_card_id UUID NOT NULL REFERENCES issue_cards(id),
    original_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT,
    overridden_by_contact_id UUID REFERENCES contacts(id),
    overridden_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.12 `resolutions`

```sql
CREATE TABLE resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_card_id UUID NOT NULL REFERENCES issue_cards(id),
    resolution_action TEXT,
    resolved_by_contact_id UUID REFERENCES contacts(id),
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolution_time_hours NUMERIC(10,2),
    classification_correct BOOLEAN,
    manager_feedback TEXT
);
```

### 4.13 `outbound_messages`

```sql
CREATE TABLE outbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    trade_schedule_item_id UUID REFERENCES trade_schedule_items(id),
    contact_id UUID REFERENCES contacts(id),
    channel TEXT NOT NULL,
    provider_message_id TEXT,
    body TEXT,
    purpose TEXT,
    quiet_hours_override BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at TIMESTAMPTZ,
    delivery_status TEXT,
    raw_provider_response JSONB
);
```

---

## 5. Plivo Intake

### Inbound SMS/MMS

Configure the Plivo application Message URL to point to:

```text
POST /webhooks/plivo/message
```

Expected handling:

1. Validate Plivo signature
2. Extract sender, destination, text, message UUID, and media
3. Store raw payload and media references
4. De-duplicate using provider message UUID
5. Enqueue `process_inbound_message`
6. Return `200 OK` immediately

### Inbound Voice

Routes:

```text
POST /webhooks/plivo/voice
POST /webhooks/plivo/recording
```

Voice flow:
1. Answer with a short prompt
2. Record voicemail
3. Receive recording callback
4. Store original audio
5. Enqueue transcription
6. Feed transcript into the same inbound pipeline

### Outbound

All outbound SMS and notifications use a provider adapter:

```python
class MessagingProvider:
    async def send_message(...)
    async def send_media(...)
    async def get_delivery_status(...)
```

The business layer must not call Plivo directly.

This keeps provider replacement possible.

---

## 6. Inbound Processing Pipeline

```python
async def process_inbound_message(message_id: UUID) -> None:
    message = await inbound_repo.get(message_id)

    context = await context_resolver.resolve(message)

    language_grade = await keyword_classifier.grade(
        text=message.normalized_text,
        context=context
    )
    await audit_repo.save_language_grade(language_grade)

    if language_grade.ai_required:
        event_payload = await ai_interpreter.extract_event(
            message=message,
            context=context,
            language_grade=language_grade
        )
    else:
        event_payload = deterministic_parser.parse(
            message=message,
            context=context
        )

    event = await event_repo.create(event_payload)

    project_context = await project_context_service.load(event.project_id)

    flow_grade = flow_engine.evaluate(
        event=event,
        project_context=project_context,
        language_grade=language_grade
    )
    await audit_repo.save_flow_grade(flow_grade)

    if flow_grade.status in {"yellow", "red"}:
        card = await card_generator.create(
            event=event,
            flow_grade=flow_grade,
            project_context=project_context
        )
        await card_repo.upsert_open_card(card)

    await notification_service.apply(flow_grade, event, project_context)
```

---

## 7. AI Structured Output

AI must return JSON only.

```json
{
  "event_type": "trade_delayed",
  "trade": "electrical_rough",
  "summary": "Electrical crew cannot start tomorrow",
  "reason": "crew unavailable",
  "original_date": "2026-07-22",
  "revised_date": null,
  "certainty": "confirmed",
  "requires_clarification": true,
  "clarification_question": "What is the earliest date your crew can start?"
}
```

AI output must be schema-validated before it is accepted.

Invalid output:
- Retry once with a repair prompt
- If still invalid, place in review queue
- Never create Red solely from an invalid AI response

---

## 8. Flow Engine

The Flow Engine must be deterministic and testable.

### Inputs
- Structured event
- Schedule maturity
- Date authority
- Dependencies
- Next confirmed trade
- Inspections
- Deadlines
- Current project phase
- Critical-path flag
- Open issues
- Company escalation rules

### Example Rules

```text
IF work_blocked = true
THEN Red

IF active downstream crew cannot proceed
THEN Red

IF confirmed inspection is blocked within 24 hours
THEN Red

IF confirmed trade start is missed AND critical_path = true
THEN Red

IF target date is threatened AND no confirmed dependency is blocked
THEN Yellow

IF estimated date moves AND no operational commitment is affected
THEN Green or no card

IF schedule data is incomplete AND event requires action
THEN Yellow

IF message confirms on-track progress
THEN Green or no card
```

Every grade must include:
- Rule identifier
- Explainable reason
- Confidence
- Missing information

---

## 9. Project Onboarding

Routes:

```text
GET  /projects/new
POST /projects
GET  /projects/{id}/edit
POST /projects/{id}/contacts
POST /projects/{id}/schedule-items
```

### UX Requirements
- Add Project beside Add Contact
- Progressive disclosure
- Trade schedule optional
- Save as Draft
- Create Project
- Add contact inline
- No issue cards during onboarding
- Schedule maturity computed after save

### Schedule Maturity Calculation

```python
def calculate_schedule_maturity(project, items):
    if not items and not project.estimated_start and not project.target_start:
        return "no_schedule"
    if items and all(i.estimated_start and not i.target_start for i in items):
        return "estimated_only"
    if any(i.target_start for i in items) and not dependencies_complete(items):
        return "target_schedule"
    if has_some_dependencies(items):
        return "partial_schedule"
    if dates_and_dependencies_complete(items):
        return "full_schedule"
    return "partial_schedule"
```

---

## 10. Dashboard

### Sorting
- Red before Yellow
- Within each color, oldest unresolved first

### Card Data
- City
- Address
- Trade
- Event summary
- Impact summary
- Age
- Source channel
- Recommended action

### Actions
- Resolve
- Date
- Call
- Delegate

No additional dashboard buttons are required.

### Date Action
Return one of:
- `no_date_change`
- `change_this_trade_only`
- `change_this_trade_and_next_trade`
- `cascade_selected_trades`
- `manual_review_required`

Confirmed dates always require manager approval and notification.

---

## 11. Quiet Hours and Rate Limiting

### Quiet Hours
- 7:00 AM–7:00 PM local project timezone
- Red emergency notifications may bypass
- Inbound always accepted

### Rate Limit
- One automated proactive SMS per project/trade/day
- Clarification replies do not count as proactive outreach
- Manager-triggered messages are allowed
- Issue responses may continue until context is resolved

Store rate limits in PostgreSQL.

---

## 12. Integrations

### MVP
- Provider-neutral webhook interface
- Public internal API
- Outbound event hooks
- CSV import

### Next
- Zapier
- Buildertrend
- JobTread
- Procore
- Contractor Foreman
- Fieldwire
- Google Calendar
- Microsoft 365

### Integration Contract

External systems may provide:
- Project identity
- Address
- Contacts
- Trade schedule
- Estimated, target, or confirmed dates
- Current phase
- Inspection dates
- Status changes

The system must record source provenance for every imported field.

---

## 13. Monitoring and Audit

Track:
- Webhook success rate
- Duplicate inbound rate
- Unknown sender rate
- AI invocation rate
- AI parsing failure rate
- Language Grade vs Flow Grade differences
- Manager override rate
- False positive rate
- False negative rate
- Resolution time
- Message cost
- Transcription cost
- Delivery failures

Health endpoints:
- `/health/live`
- `/health/ready`

---

## 14. Security

- Validate Plivo signatures
- Validate inbound email signatures where supported
- Encrypt secrets
- Store media in private object storage
- Use signed URLs for playback
- Apply role-based dashboard access
- Avoid exposing raw phone numbers in logs
- Retain raw provider payloads under a defined retention policy
- Support contact opt-out and messaging compliance requirements

---

## 15. Implementation Order

### Phase 1
- Revised database schema
- Project onboarding
- Contact assignment
- Event/audit foundation

### Phase 2
- Plivo inbound and outbound SMS
- Keyword classifier
- Simple structured replies
- Yellow/Red dashboard

### Phase 3
- AI interpretation
- Separate Language Grade and Flow Grade
- Manager override
- Resolution analytics

### Phase 4
- MMS
- Voice recording and transcription
- Email intake
- Date actions and selective cascade

### Phase 5
- Public API
- Zapier connector
- First contractor-platform integration

---

## 16. Acceptance Test

A passing end-to-end test:

1. PM creates a project with address, Estimated Start, Target Start, and assigned contacts
2. Electrical trade has a target start date
3. Electrical subcontractor texts the Plivo number: "We cannot start tomorrow. Earliest is Thursday."
4. Plivo webhook stores and queues the message
5. Keyword classifier stores Language Grade
6. AI extracts the structured event
7. Flow Engine evaluates project schedule
8. Yellow or Red is assigned based on actual downstream impact
9. Card appears with address, trade, issue, impact, and recommended action
10. PM calls the trade, changes dates, delegates, or resolves
11. All stages remain preserved in the audit history
