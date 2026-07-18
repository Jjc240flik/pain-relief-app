# TLG Andon — SMS-Powered Issue Tracking for Home Builders

A real-time issue tracking system designed for home builders. Subcontractors report problems via **SMS**, **Email**, or **Voice**, and the system classifies them, alerts the Project Manager, and tracks resolution — all without requiring anyone to install an app.

## Architecture

```
andon/                          # Main application
├── app/
│   ├── api/                    # Admin & public API routes
│   │   ├── admin.py            # Analytics, scorecard, contacts, alerts, keyword import
│   │   ├── seed.py             # Seed data generation
│   │   └── schedule.py         # Schedule management
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── contact.py          # Subcontractor contacts
│   │   ├── event.py            # Immutable event log (SMS, Email, Voice, MMS)
│   │   ├── house.py            # House/project data
│   │   └── schedule_item.py    # Per-trade schedule items with andon status
│   ├── repositories/           # Data access layer
│   ├── services/               # Business logic
│   │   ├── classifier.py       # ClassifierEngine v3 (trade-aware, keyword-based)
│   │   ├── inbound.py          # Inbound message processor
│   │   ├── keyword_loader.py   # Graded keyword import from Excel
│   │   ├── media_store.py      # Download & store MMS media (S3 or local)
│   │   ├── outbound.py         # Outbound message sender
│   │   ├── scheduler.py        # Automated check-in scheduler
│   │   └── transcriber.py      # Voice transcription via OpenAI Whisper
│   ├── templates/              # Jinja2 templates
│   │   ├── admin/              # Analytics, alerts, scorecard, contacts
│   │   ├── onboarding/         # New-user setup wizard
│   │   └── partials/           # HTMX partials (dashboard cards)
│   ├── views/                  # Dashboard + onboarding routes
│   │   ├── dashboard.py        # Main dashboard with cards
│   │   └── onboarding.py       # New-client onboarding wizard
│   └── webhooks/               # Inbound webhook handlers
│       ├── twilio.py           # SMS, MMS, Voice
│       └── sendgrid.py         # Email
├── docs/
│   └── admin-monitoring-system.md
├── keywords_and_phrases.md           # Keyword reference (markdown)
├── keywords_and_phrases_checklist.xlsx # Graded keyword Excel
├── keywords_rules.json                # Classifier graded rules
├── alerts_config.json                 # Usage alert thresholds
├── escalation_config.json             # Escalation group config
├── docker-compose.yml                 # PostgreSQL + app
├── pyproject.toml                     # Python dependencies
└── New_Features.md                    # Feature backlog (active + completed)
```

## Key Features

### Ingest (Multi-Channel)
- **SMS** — Twilio webhook, structured reply detection (1=Yes, 2=No, 3=Issue)
- **MMS** — Up to 5 photos + video per message, gallery modal
- **Email** — SendGrid Inbound Parse, sender resolution by email
- **Voice** — Voicemail recording + Whisper transcription

### Classification (ClassifierEngine v3)
- Trade-aware severity matrix (1.3–0.85 multipliers)
- Multi-hit scoring (3+ Yellow keywords → Red upgrade)
- Graded keyword import from Excel (420 terms across 10 trades)
- Option B+C behind detection (check-in verification + history tracking)
- Feedback widget for PM corrections (logged for future retraining)

### Dashboard
- Real-time card view sorted oldest-first
- Activity labels (Onsite, Behind, Issue Reported, Message Received)
- Quick actions: Resolve, +1/+3 Days, Date picker, Call (sub/boss/email), Delegate, Escalate
- Contextual trade-specific actions (Check Truss, Call Supplier, Flag Cleanup, etc.)
- Inline classification correction (R/Y/G picker with optional comment)
- Media gallery (photos) + video player
- Escalation banners (time-based, multi-Red, keyword-triggered)

### Admin Tools
- **Analytics** — Usage metrics, cost estimates, issue insights, system health
- **Alerts** — Configurable thresholds for spend, volume, storage
- **Scorecard** — Per-subcontractor performance metrics
- **Contacts** — CRUD + CSV import
- **Onboarding** — New-user wizard with template download

## Quick Start

```bash
cd andon
cp .env.example .env        # Edit with your Twilio/SendGrid/OpenAI keys
docker compose up -d        # Start PostgreSQL
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Seed Data
```bash
curl -X POST http://localhost:8000/api/seed
```

### Routes

| Path | Purpose |
|---|---|
| `/dashboard` | Main PM dashboard |
| `/onboarding` | New-client setup wizard |
| `/admin/analytics` | Usage & cost analytics |
| `/admin/alerts` | Alert configuration |
| `/admin/scorecard` | Subcontractor scorecard |
| `/admin/contacts` | Contact management |
| `/admin/import-keywords` | Import graded Excel keywords |
| `/webhooks/twilio/sms` | Twilio SMS/MMS inbound |
| `/webhooks/twilio/voice` | Twilio Voice inbound |
| `/webhooks/twilio/recording` | Twilio recording callback |
| `/webhooks/sendgrid/inbound` | SendGrid email inbound |

## Tech Stack

- **Python 3.12** + **FastAPI** — Backend
- **PostgreSQL 16** — Database
- **Jinja2** + **HTMX** + **Tailwind CSS** — Frontend
- **Twilio** — SMS, MMS, Voice
- **SendGrid** — Email inbound
- **OpenAI Whisper** — Voice transcription
- **OpenPyXL** — Excel file processing
- **SQLAlchemy** — ORM
