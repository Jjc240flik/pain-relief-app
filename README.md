# TLG Andon

TLG Andon is a flow-intelligence and issue-orchestration platform for residential builders managing multiple active homes.

Subcontractors and field personnel report updates through familiar channels such as SMS, MMS, email, voicemail, or manual entry. The backend converts those inputs into structured construction events, evaluates schedule impact, and shows project managers only the Yellow and Red exceptions requiring attention.

The system does not require subcontractors to install an app.

## Product Position

TLG Andon is not a replacement for Buildertrend, JobTread, Procore, or another system of record.

It is a **system of attention** that can sit beside or integrate with existing contractor platforms.

## Core Flow

```text
SMS / MMS / Email / Voice / Manual / Integration
                        ↓
               Raw Intake + Audit Log
                        ↓
             Keyword / Phrase Classifier
                        ↓
              AI Interpretation if Needed
                        ↓
             Structured Construction Event
                        ↓
          Schedule Context + Dependency Rules
                        ↓
                    Flow Grade
                        ↓
             Yellow / Red Dashboard Card
                        ↓
          Resolve / Date / Call / Delegate
```

## Architecture

```text
andon/
├── app/
│   ├── api/
│   │   ├── admin.py
│   │   ├── contacts.py
│   │   ├── projects.py
│   │   ├── schedule.py
│   │   ├── integrations.py
│   │   └── seed.py
│   ├── models/
│   │   ├── project.py
│   │   ├── project_contact.py
│   │   ├── contact.py
│   │   ├── trade_schedule_item.py
│   │   ├── inbound_message.py
│   │   ├── construction_event.py
│   │   ├── grading_result.py
│   │   ├── issue_card.py
│   │   ├── manager_override.py
│   │   ├── resolution.py
│   │   └── outbound_message.py
│   ├── repositories/
│   ├── services/
│   │   ├── intake.py
│   │   ├── context_resolver.py
│   │   ├── keyword_classifier.py
│   │   ├── ai_interpreter.py
│   │   ├── flow_engine.py
│   │   ├── card_generator.py
│   │   ├── date_engine.py
│   │   ├── contact_router.py
│   │   ├── outbound.py
│   │   ├── scheduler.py
│   │   ├── transcriber.py
│   │   ├── media_store.py
│   │   └── audit.py
│   ├── templates/
│   │   ├── dashboard/
│   │   ├── contacts/
│   │   ├── projects/
│   │   ├── onboarding/
│   │   └── partials/
│   ├── views/
│   │   ├── dashboard.py
│   │   ├── contacts.py
│   │   ├── projects.py
│   │   └── onboarding.py
│   └── webhooks/
│       ├── plivo.py
│       ├── email.py
│       └── integrations.py
├── docs/
│   ├── PRD.md
│   ├── TECH_SPEC.md
│   └── admin-monitoring-system.md
├── keywords_and_phrases_checklist.xlsx
├── keyword_rules.json
├── escalation_config.json
├── docker-compose.yml
└── pyproject.toml
```

## Key Features

### Multi-Channel Intake
- SMS through Plivo
- MMS photos and media
- Email inbound parsing
- Voicemail and voice-note transcription
- Manual PM entry
- Future integration webhooks

### Project Onboarding
- Add Project beside Add Contact
- Estimated Start and Target Start
- Optional trade schedule
- Project-specific contacts
- Partial schedule support
- Schedule maturity tracking

### Classification
- Existing graded keyword and phrase library
- Trade-aware matching
- Simple reply bypass
- AI interpretation for free-form or ambiguous language
- Separate Language Grade and Flow Grade
- Manager override and feedback logging

### Flow Engine
- Uses project schedule maturity
- Evaluates target and confirmed dates
- Checks downstream trades and inspections
- Applies deterministic rules
- Produces explainable Yellow and Red outcomes

### Dashboard
- Yellow and Red cards only by default
- Oldest unresolved cards first
- City, address, trade, issue, impact, and age
- Resolve, Date, Call, Delegate
- Media playback and message source
- No extra front-end controls for backend intelligence

### Integrations
- Public API-ready design
- Webhook intake and outbound events
- Future Zapier support
- Future Buildertrend, JobTread, Procore, Contractor Foreman, Fieldwire, and calendar connectors

## Technology Stack

- Python 3.12
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.x
- Alembic
- Jinja2
- HTMX
- Tailwind CSS
- Plivo Messaging and Voice
- OpenAI transcription / language interpretation
- OpenPyXL
- Object storage for media
- Background job queue

## Quick Start

```bash
cd andon
cp .env.example .env
docker compose up -d
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Core Routes

| Path | Purpose |
|---|---|
| `/dashboard` | Daily Yellow/Red attention view |
| `/projects` | Project list and administration |
| `/projects/new` | Add Project onboarding |
| `/contacts` | Contact management |
| `/contacts/new` | Add Contact |
| `/admin/analytics` | Usage, classification, and cost analytics |
| `/admin/alerts` | Alert and escalation configuration |
| `/admin/scorecard` | Subcontractor metrics |
| `/admin/import-keywords` | Import graded keyword file |
| `/webhooks/plivo/message` | Inbound SMS/MMS |
| `/webhooks/plivo/voice` | Inbound voice |
| `/webhooks/plivo/recording` | Recording callback |
| `/webhooks/email/inbound` | Inbound email |
| `/webhooks/integrations/{source}` | Future integration intake |
| `/api/v1/projects` | Project API |
| `/api/v1/events` | Event API |
| `/api/v1/cards` | Card API |

## Build Philosophy

- Cards are temporary; events are permanent
- AI translates; deterministic rules decide
- Missing schedules produce conservative grading
- Confirmed dates are never silently changed
- The frontend remains simple even as the backend becomes more capable
- Integrations should reduce duplicate work, not create another platform burden
