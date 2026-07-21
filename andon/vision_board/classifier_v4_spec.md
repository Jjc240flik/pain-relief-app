# Classification Engine v4 — Specification

**Author:** System design input  
**Date:** July 2026  
**Purpose:** Define how the Flow Impact Engine converts field information into structured construction events with Green/Yellow/Red classification.

---

## Core Philosophy

The incoming message itself does not determine severity. Severity is determined by the **operational impact** of the event.

The system must distinguish between:

- No schedule
- Estimated dates only
- Target dates (operational intentions)
- Confirmed dates (committed)
- Actual dates (in progress / completed)

A rough estimated date is not a committed target date. A target date is not a confirmed subcontractor commitment.

---

## Schedule Maturity Model

| Maturity | Description |
|---|---|
| `no_schedule` | No usable date or dependency info |
| `estimated_only` | Planning dates only, no targets or confirmed |
| `target_schedule` | One or more trades have target dates, not all confirmed |
| `partial_schedule` | Some dates/dependencies known, full sequence incomplete |
| `full_schedule` | Enough dated milestones to evaluate downstream impact |

---

## Date Hierarchy (strongest to weakest)

1. Actual date (work physically began)
2. Confirmed date (direct commitment from trade)
3. Target date (operational intention)
4. Estimated date (planning context)
5. No date

---

## Event Extraction

Standardized event types:

- trade_confirmed / trade_delayed / trade_cancelled / trade_no_show
- trade_on_site / work_started / work_completed / work_incomplete / work_blocked
- estimated_date_changed / target_date_changed / confirmed_date_changed
- inspection_scheduled / inspection_failed / inspection_passed
- material_delayed / material_missing / material_delivered
- access_issue / weather_delay / crew_shortage / safety_issue / quality_issue
- permit_issue / change_required / unknown_issue

---

## Status Rules

### GREEN / No Card
- Work on track
- No downstream impact
- Informational only, no action needed
- Delay exists but verified float absorbs it
- Only estimated date shifted, no operational commitment affected

### YELLOW
- Manager attention required
- Trade reports delay
- Target date threatened
- Confirmed start date may be missed
- Work incomplete but production not stopped
- Material/crew issue may affect schedule
- Sub has not responded within response window
- Partial/missing schedule prevents reliable assessment
- Issue has remained unresolved long enough to require monitoring

### RED
- Production currently blocked
- Crew on site and cannot proceed
- Confirmed trade failed to arrive, critical path affected
- Inspection failure prevents next phase
- Safety or compliance issue
- Closing/turnover deadline at immediate risk
- Downstream trade scheduled imminently and blocked
- Company-defined Red rule triggered
- Yellow exceeded permitted float/escalation time

---

## Time-Based Escalation

- Estimated date approaching, no target → Yellow planning reminder
- Target date within 72h, no confirmation → Yellow
- Target date missed → Yellow (unless production blocked)
- Confirmed start within 24h, no response → Yellow
- Confirmed start missed → Red if critical path affected, else Yellow
- Yellow unresolved beyond float → Red
- Yellow unresolved 24h → keep Yellow unless impact grows
- Yellow unresolved 48h → reassess schedule/dependencies

---

## AI Constraints

**May:**
- Interpret natural language messages
- Extract dates, trades, reasons, commitments
- Identify date type (estimated/target/confirmed/actual)
- Classify event and downstream impact
- Calculate confidence
- Recommend follow-up questions
- Suggest date changes
- Identify appropriate project contacts

**Must not:**
- Invent schedules, trade dependencies, contacts, costs, or closing impacts
- Silently change confirmed dates
- Claim production is blocked without evidence
- Mark Red solely because negative words appear
- Treat every delay as critical

---

## Classification Output Schema

See `classifier_v4_schema.json` for the full JSON schema.

Key fields:
- `schedule.schedule_maturity` — what kind of schedule exists
- `schedule.operative_date_type` — actual/confirmed/target/estimated/none
- `event.event_type` — standardized event type
- `event.certainty` — confirmed/likely/possible/unclear
- `impact.production_blocked` — boolean
- `classification.status` — green/yellow/red
- `classification.confidence_score` — 0.0-1.0
- `classification.grading_rule_used` — which rule triggered
- `recommended_action.*` — who to contact, what to do
- `foreman_card.*` — 5-second card for the superintendent

---

## Key Design Decisions

1. **Schedule maturity gates everything.** Without knowing what kind of schedule exists, severity cannot be assessed.
2. **Date type matters more than the date value.** An estimated date that shifts is not the same as a confirmed date that slips.
3. **Downstream impact must be explicit.** "Could affect" is not the same as "will block."
4. **The foreman card must answer in 5 seconds:** What happened? Why does it matter? What do I do?
5. **When uncertain, surface the issue, state what's missing, and give the simplest next action.**
