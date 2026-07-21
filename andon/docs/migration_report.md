# Migration Report: TLG Andon — Architecture Alignment

**Date:** July 21, 2026
**Author:** Lead Architect
**Status:** Review Complete — No Code Changes Yet

---

## 1. Executive Summary

The current codebase (v0.x) was built as a proof-of-concept SMS Andon system for a single builder. The three source-of-truth documents (PRD.md, README.md, TECH_SPEC.md) describe a **multi-tenant flow intelligence platform** with fundamentally different architecture.

Approximately **70% of the current code requires refactoring or replacement** to align with the new spec.

| Category | Existing | Spec Requires | Match |
|---|---|---|---|
| Database tables | 13 (houses, schedule_items, events, etc.) | ~15 tables (projects, trade_schedule_items, inbound_messages, construction_events, flow_grades, issue_cards, etc.) | ~30% |
| Services | 9 (classifier, inbound, outbound, etc.) | 14+ (intake, context_resolver, keyword_classifier, ai_interpreter, flow_engine, card_generator, date_engine, contact_router, audit) | ~40% |
| Models | 6 (house, schedule_item, event, contact, designer_log) | 12+ (project, contact, trade_schedule_item, inbound_message, construction_event, grading_result, issue_card, manager_override, resolution, outbound_message) | ~20% |
| API routes | Ad-hoc, no versioning | RESTful, versioned (/api/v1/) | 10% |
| Webhooks | Synchronous processing | Queue-based async processing | 30% |
| Frontend | Dashboard has extra buttons | Only Resolve, Date, Call, Delegate | 60% |
| Documentation | Old PRD.md, no TECH_SPEC | New PRD, README, TECH_SPEC | 0% |

---

## 2. What Remains Unchanged

These components align with the spec and can be preserved:

- **Plivo webhook structure** — `/webhooks/plivo/*` is the correct approach. Endpoint paths need minor renaming (`/sms` → `/message`).
- **Existing keyword classifier** (`classifier.py`) — The graded keyword library, trade-aware matching, and simple-reply handling remain the first classification layer. This becomes `keyword_classifier.py` in the new architecture.
- **Transcriber service** (`transcriber.py`) — OpenAI Whisper integration is correct. Keep as-is.
- **Media store service** (`media_store.py`) — S3-compatible storage is correct. Keep as-is.
- **Outbound service** (`outbound.py`) — Provider-adapter pattern is correct. Refactor to implement `MessagingProvider` interface.
- **Auth service** (`auth.py`) — Session-based auth is fine for MVP.
- **Onboarding templates** (`welcome.html`, `add.html`, `import.html`) — Contact onboarding flow is correct.
- **Admin analytics page** (`/admin/analytics`) — Usage monitoring is correct.
- **Jinja2 + HTMX + Tailwind** frontend stack — Correct for MVP.
- **PostgreSQL + SQLAlchemy async** — Correct.

---

## 3. What Requires Refactoring

### 3.1 Database Schema — Major Refactor

**Current → Target mapping:**

| Current Table | Target Table | Action |
|---|---|---|
| `houses` | Remove. Replaced by `projects`. Migrate address/city/state data to `projects`. | **Migration + deprecation** |
| `schedule_items` | Remove. Replaced by `trade_schedule_items`. Migrate trade/date/status data to new model. | **Migration + deprecation** |
| `events` | Split into `inbound_messages` + `construction_events` + `language_grades` + `flow_grades` | **Migration** |
| `contacts` | Add missing fields: `company_id`, `manager_name`, `preferred_contact_method`, `is_escalation_contact` | **Migration** |
| `projects` (current) | Add missing fields: `company_id`, `lot_number`, `zip_code`, `community`, `internal_project_number`, `assigned_pm_contact_id`, `assigned_superintendent_contact_id`, `estimated_start`, `target_start`, `actual_start`, `estimated_completion`, `target_completion`, `actual_completion`, `schedule_maturity` | **Migration** |
| `project_contacts` | Add missing fields: `is_primary`, `is_escalation`, `assignment_status`, `UNIQUE` constraint | **Migration** |
| `project_trades` | Rename to `trade_schedule_items`. Add: `confirmed_start`, `actual_start`, `confirmed_completion`, `actual_completion`, `preceding_trade_item_id`, `critical_path`, `inspection_required`, `schedule_status` | **Migration + rename** |
| *(new)* | `trade_dependencies` | **Create** |
| *(new)* | `inbound_messages` | **Create** |
| *(new)* | `language_grades` | **Create** |
| *(new)* | `construction_events` | **Create** |
| *(new)* | `flow_grades` | **Create** |
| *(new)* | `issue_cards` | **Create** |
| *(new)* | `manager_overrides` | **Create** |
| *(new)* | `resolutions` | **Create** |
| *(new)* | `outbound_messages` | **Create** |

### 3.2 Models — Major Refactor

| Current File | Action |
|---|---|
| `models/house.py` | **Deprecate.** Data moves to `models/project.py`. Remove after data migration. |
| `models/schedule_item.py` | **Deprecate.** Replaced by `models/trade_schedule_item.py`. Remove after data migration. |
| `models/event.py` | **Deprecate.** Replaced by multiple model files. |
| `models/contact.py` | **Refactor** — add spec fields, change model name to match spec. |
| `models/designer_log.py` | Keep. |
| *(new)* `models/project.py` | **Create** — full project model with all spec fields. |
| *(new)* `models/project_contact.py` | **Create** — junction model with spec fields. |
| *(new)* `models/trade_schedule_item.py` | **Create** — replaces schedule_item.py. |
| *(new)* `models/trade_dependency.py` | **Create** — dependency tracking. |
| *(new)* `models/inbound_message.py` | **Create** — raw intake storage. |
| *(new)* `models/language_grade.py` | **Create** — keyword classifier output. |
| *(new)* `models/construction_event.py` | **Create** — structured event. |
| *(new)* `models/flow_grade.py` | **Create** — deterministic flow evaluation. |
| *(new)* `models/issue_card.py` | **Create** — PM-facing card. |
| *(new)* `models/manager_override.py` | **Create** — override audit. |
| *(new)* `models/resolution.py` | **Create** — resolution tracking. |
| *(new)* `models/outbound_message.py` | **Create** — outbound audit. |

### 3.3 Services — Refactor + Create

| Current File | Action |
|---|---|
| `services/classifier.py` | **Rename to `keyword_classifier.py`** and refactor to produce `LanguageGrade` output. |
| `services/inbound.py` | **Refactor** to delegate to `intake.py`, `context_resolver.py`, etc. Keep pipeline orchestration here. |
| `services/outbound.py` | **Refactor** to implement `MessagingProvider` interface. |
| `services/keyword_loader.py` | Keep. |
| `services/media_store.py` | Keep. |
| `services/transcriber.py` | Keep. |
| `services/scheduler.py` | Keep. |
| `services/auth.py` | Keep. |
| *(new)* `services/intake.py` | **Create** — normalize incoming messages. |
| *(new)* `services/context_resolver.py` | **Create** — resolve project, trade, contact context. |
| *(new)* `services/ai_interpreter.py` | **Create** — AI structured output extraction. |
| *(new)* `services/flow_engine.py` | **Create** — deterministic flow grading rules. |
| *(new)* `services/card_generator.py` | **Create** — create/update issue cards. |
| *(new)* `services/date_engine.py` | **Create** — date authority + cascade logic. |
| *(new)* `services/contact_router.py` | **Create** — find appropriate contact for notifications. |
| *(new)* `services/audit.py` | **Create** — immutable audit trail. |

### 3.4 Webhooks — Refactor

| Current File | Action |
|---|---|
| `webhooks/plivo.py` | **Rename `/sms` to `/message`**. Add async queue pattern (store → return 200 → process). Refactor voice handling. |
| `webhooks/sendgrid.py` | Keep, rename path to `/webhooks/email/inbound`. |
| `webhooks/twilio.py` | **Remove** — deprecated in favor of Plivo. Confirm nothing references it. |

### 3.5 Views — Refactor

| Current File | Action |
|---|---|
| `views/dashboard.py` | **Simplify** — remove extraneous buttons. Keep only Resolve, Date, Call, Delegate. Remove escalation banners, push groups, contextual actions, feedback widget from the daily view. |
| `views/onboarding.py` | **Refactor** — align with spec: move to `api/projects.py`, add trade schedule, contact assignment, schedule maturity calculation. |

### 3.6 API Routes — Restructure

| Current Route | Action |
|---|---|
| `POST /webhooks/twilio/*` | Remove |
| `POST /webhooks/plivo/sms` | Rename to `/webhooks/plivo/message` |
| `GET /dashboard/partial` | Keep but simplify response |
| `POST /dashboard/{id}/resolve` | Keep |
| `POST /dashboard/{id}/push?days=1` | Remove — not in spec |
| `POST /dashboard/{id}/push-custom` | Keep as Date action |
| `POST /dashboard/{id}/delegate` | Keep |
| `POST /dashboard/{id}/delegation-update` | Keep |
| `POST /dashboard/classify/{id}/correct` | Keep (feedback) |
| *(new)* `/api/v1/projects` | Create |
| *(new)* `/api/v1/events` | Create |
| *(new)* `/api/v1/cards` | Create |

---

## 4. What Should Be Removed

### 4.1 Remove After Data Migration
- `models/house.py`
- `models/schedule_item.py`
- `models/event.py`
- `tables: houses, schedule_items, events` (old schema)

### 4.2 Remove Immediately (Dead or Obsolete)
- `webhooks/twilio.py` — Replaced by Plivo
- `partials/escalation_banners.html` — Already removed from dashboard
- `templates/admin/escalations.html` — Feature removed
- `escalation_config.json` — Feature removed
- `app/repositories/house_repo.py` — Deprecated with houses table
- `app/repositories/schedule_repo.py` — Deprecated with schedule_items table

### 4.3 Dashboard Buttons to Remove (per spec)
- `+` push button — Not in spec's four actions
- `📞 Call ▾` dropdown with multi-options — Simplify to single Call
- Contextual quick actions (Check Truss Specs, etc.) — Not in spec
- Delegation status buttons (In Progress, Resolved) — Not in spec for card
- Feedback widget (👍👎) — Not in spec for daily dashboard

### 4.4 Files to Keep
- `.env.example` (update with new vars)
- `alembic/` (migration framework stays)
- `config.py` (update with new settings)
- `main.py` (update imports)
- `database.py` (keep)
- All templates except those listed for removal
- `docs/admin-monitoring-system.md`

---

## 5. Database Migrations

### Phase 1 (Foundation)
1. Create `inbound_messages` table — start capturing raw payloads immediately
2. Create `construction_events` table — start capturing structured events
3. Add new columns to `projects`, `contacts`, `project_contacts`
4. Create `trade_schedule_items` table (parallel to `schedule_items`)

### Phase 2 (Grading)
5. Create `language_grades` table
6. Create `flow_grades` table
7. Create `issue_cards` table
8. Create `manager_overrides` table

### Phase 3 (Completion)
9. Create `resolutions` table
10. Create `outbound_messages` table
11. Create `trade_dependencies` table
12. Migrate data from `houses` → `projects`
13. Migrate data from `schedule_items` → `trade_schedule_items`
14. Migrate data from `events` → `inbound_messages` + `construction_events`

### Phase 4 (Cleanup)
15. Drop `houses`, `schedule_items`, `events` tables
16. Remove old model files
17. Update Alembic revision history

---

## 6. API Changes

### Route Renames
| Current | New |
|---|---|
| `/webhooks/plivo/sms` | `/webhooks/plivo/message` |
| `/webhooks/sendgrid/inbound` | `/webhooks/email/inbound` |

### Route Removals
| Route | Reason |
|---|---|
| `POST /webhooks/twilio/*` (all) | Deprecated provider |
| `POST /dashboard/{id}/escalate` | Already removed |
| `POST /dashboard/{id}/push?days=1` | Not in spec actions |

### New Routes
| Route | Purpose |
|---|---|
| `GET /api/v1/projects` | Public project API |
| `POST /api/v1/projects` | Create project via API |
| `GET /api/v1/cards` | Read active issue cards |
| `POST /api/v1/cards/{id}/resolve` | Resolve via API |
| `POST /api/v1/cards/{id}/override` | Manager override |
| `GET /api/v1/events` | Event query API |
| `POST /webhooks/integrations/{source}` | Future integration intake |

---

## 7. Frontend Changes

### Dashboard Simplification
- Remove `+` push button
- Simplify Call to single action (remove dropdown with multi-options)
- Remove contextual quick action section
- Remove delegation status buttons (In Progress, Resolved)
- Remove feedback widget (👍👎)
- Remove push group with Send confirmation
- Card format: keep address, trade, issue, impact, age, recommended action
- Only four actions: Resolve, Date, Call, Delegate

### New Pages
- `/projects/list` — Project list page
- `/projects/new` — Project onboarding
- `/projects/{id}` — Project detail
- `/projects/{id}/schedule` — Trade schedule management

### Admin Pages to Remove
- `/admin/escalations` — Feature removed
- `partials/escalation_banners.html` — Already dead

---

## 8. Backend Changes

### Processing Pipeline
The single biggest architectural change: **webhooks must not block on processing**.

Current flow (synchronous):
```
Webhook receive → Process message → Classify → Create event → Create card → Return 200
```

Target flow (async queue):
```
Webhook receive → Store raw payload → Enqueue job → Return 200 immediately
                                         ↓
                                  Queue worker processes:
                                    - Normalize message
                                    - Resolve context
                                    - Run keyword classifier
                                    - Store Language Grade
                                    - Run AI interpretation (if needed)
                                    - Create Construction Event
                                    - Evaluate Flow Grade
                                    - Create/update Issue Card
                                    - Apply notifications
```

### Service Dependencies
```
webhooks/plivo.py
       ↓ (enqueue)
intake.py → inbound_messages table
       ↓
context_resolver.py → resolve project, trade, contact
       ↓
keyword_classifier.py → language_grades table
       ↓ (if needed)
ai_interpreter.py → construction_events table
       ↓
flow_engine.py → flow_grades table
       ↓
card_generator.py → issue_cards table
       ↓
contact_router.py + outbound.py → notifications
```

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Data loss during migration** (houses→projects, events→inbound_messages) | High | Run new tables in parallel with old. Dual-write during migration window. |
| **Processing latency change** (sync→async) | Medium | Queue adds 1-5s delay. Acceptable for SMS. May need WebSocket push for instant dashboard updates. |
| **Dashboard simplification** removes features users rely on | Medium | Confirm with Jimmy which buttons he actually uses before removing. |
| **Webhook path change** (`/sms` → `/message`) | Low | Update Plivo dashboard configuration simultaneously. |
| **Model refactoring** breaks existing queries | High | Keep old models as read-only during transition. Build new models. Migrate one route at a time. |
| **New tables with no data** before migration | Low | Backfill from old tables as part of migration. |
| **Contact phone masking** (hex-encoded in psql display) | Low | Verify actual stored values before migration scripts. |

---

## 10. Recommended Implementation Order

### Sprint 1 — Foundation (Database + Models)
1. Write new PRD.md, README.md, TECH_SPEC.md to repo
2. Create new model files (inbound_message, construction_event, flow_grade, etc.)
3. Create new database tables via Alembic migrations
4. Add missing columns to existing tables (projects, contacts)
5. Implement `intake.py` service
6. Implement `context_resolver.py` service
7. Begin writing to new tables from existing webhooks (dual-write)

### Sprint 2 — Pipeline Restructure (Services)
8. Implement `keyword_classifier.py` (rename + refactor from classifier.py)
9. Implement `ai_interpreter.py` (structured output extraction)
10. Implement `flow_engine.py` (deterministic rules)
11. Implement `card_generator.py`
12. Implement `audit.py` service
13. Wire up async queue pattern (Redis + RQ or Dramatiq)
14. Refactor webhooks for async processing

### Sprint 3 — Frontend + Integration (Views)
15. Simplify dashboard (remove extra buttons)
16. Refactor project onboarding to match spec
17. Remove deprecated views (escalations, old onboarding paths)
18. Implement `/api/v1/` routes
19. Data migration: houses→projects, schedule_items→trade_schedule_items, events→new tables
20. Remove old models and tables

### Sprint 4 — Polish (Cleanup)
21. Remove dead code (twilio.py, house_repo.py, etc.)
22. Update documentation
23. Verify Plivo webhooks with new async flow
24. End-to-end acceptance test
25. Deploy

---

## 11. Recommendation

**Do not begin implementation until this report has been reviewed.**

The codebase has grown organically through rapid iteration. The three source-of-truth documents describe a more mature architecture that will support the long-term vision.

The single most important architectural change is **async webhook processing**. Without it, the system will not scale to the spec's requirements for AI interpretation, transcription, and image analysis without blocking webhook responses.

The second most important change is the **immutable grading pipeline** (Language Grade → Construction Event → Flow Grade → Final Card). This preserves audit history and enables the spec's requirement that "cards are temporary, events are permanent."

The dashboard simplification (removing buttons that don't exist in the spec) should be validated with Jimmy before removal.
