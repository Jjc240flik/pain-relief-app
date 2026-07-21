# Product Evolution Report: Andon → Flow Intelligence Platform

**Date:** July 21, 2026
**Author:** Lead Architect
**Status:** Review Complete — Awaiting Approval

---

## 1. Executive Summary

The product has evolved from a single-company SMS Andon prototype into a multi-tenant Flow Intelligence Platform. The codebase still reflects the original prototype in ~30 locations through hardcoded branding, terminology, and single-tenant assumptions.

| Category | Items Found | Impact |
|---|---|---|
| Hardcoded "TLG" references | 30+ locations | Low (easy to fix) |
| "Andon" user-facing terminology | 15+ pages | Medium (rename in templates) |
| Multi-tenant settings gaps | ~15 missing fields | High (needs schema + config) |
| Hardcoded SMS/email prefixes | 6 code locations | Medium (needs config-driven) |
| Single-company env vars | 3 vars (jim, clint, designer) | Low (deprecate gracefully) |
| Seed data tied to TLG | 1 file | Low (template-ize) |

---

## 2. Branding Changes Required

### 2.1 User-Facing Terminology

| Current Term | Recommended Term | Affected Areas |
|---|---|---|
| TLG Andon | [Company Name] Flow | Dashboard title, page titles |
| Andon System | Flow Intelligence Platform | Documentation |
| Andon Dashboard | Flow Dashboard | Dashboard page |
| Andon Status | Flow Status | Internal model field (defer rename) |
| Andon Alerts | Flow Alerts | Admin page |
| TLG Andon — Daily View | Flow Dashboard — [Company] | Dashboard header |
| Login — TLG Andon | Login — [App Name] | Login page |
| New Project — TLG Andon | New Project — [App Name] | Onboarding page |

### 2.2 Internal Terminology (Defer Rename — Low Priority)

| Current | Recommended | Rationale |
|---|---|---|
| `andon_status` (column) | `flow_status` | Database column — rename via migration |
| `app/` directory | Keep | No benefit to renaming |
| Route prefixes `/dashboard` | Keep | Users know it as the dashboard |
| `AndonStatus` in code | Keep or alias | Internal enum — can alias later |

### 2.3 Platform Naming

The platform brand should not be "TLG Andon" or "Andon." 

Recommended platform name: **Flow** (short, memorable, describes what it does).

- Platform: Flow
- Product: Flow Intelligence Platform
- Dashboard: Flow Dashboard
- Admin: Flow Admin

The `tenant_settings` table already has `company_name`. The page title should be:
```
{company_name} · Flow
```

---

## 3. Documentation Updates

### 3.1 Files Requiring Updates

| File | Changes Needed |
|---|---|
| `docs/PRD.md` | Replace "Andon System" → "Flow Intelligence Platform". Update positioning section. |
| `README.md` | Update product name, tagline, architecture diagram labels. |
| `docs/TECH_SPEC.md` | Update product name, service names that reference "Andon". |
| `docs/migration_report.md` | Minor — already references new architecture. |
| `docs/admin-monitoring-system.md` | Review for TLG/Andon references. |
| `vision_board/README.md` | Already uses "Decision Layer" language — good. Update any Andon references. |
| `new_features/*.md` | Update references from "Andon" to "Flow". |

### 3.2 Architecture Diagram Labels

In README.md, the architecture flow labels "Andon" in several places. Replace with platform-agnostic terms.

---

## 4. Multi-Tenant Improvements

### 4.1 Company Settings Model

The current `tenant_settings` table has 2 keys. The minimum viable set:

| Key | Type | Purpose |
|---|---|---|
| `company_name` | text | Already exists |
| `sms_display_name` | text | Company name for outbound SMS prefix |
| `email_signature` | text | Outbound email footer |
| `primary_color` | text | UI theme (hex) |
| `logo_url` | text | Dashboard header logo |
| `timezone` | text | Project/task timezone |
| `quiet_hours_start` | integer | Outbound quiet hours |
| `quiet_hours_end` | integer | Outbound quiet hours |
| `support_email` | text | Contact for builder support |
| `onboarding_complete` | text | Already exists |

### 4.2 Subscribers Table Enhancement

The `subscribers` table already exists with basic fields. Add branding columns:

- `brand_primary_color VARCHAR(7) DEFAULT '#2563eb'`
- `brand_logo_url TEXT`
- `sms_display_name VARCHAR(100)`
- `email_signature TEXT`
- `timezone VARCHAR(50) DEFAULT 'America/Chicago'`

### 4.3 Seed Data

The seed file (`api/seed.py`) is heavily TLG-specific. Refactor to:
- Use placeholders for company name
- Use a templated SMS prefix
- Make clear these are example contacts, not production data

---

## 5. Configuration Changes

### 5.1 Environment Variables to Deprecate

| Current Var | Reason | Replacement |
|---|---|---|
| `jim_phone_number` | TLG-specific personal phone | Remove — use contact lookup |
| `clint_phone_number` | TLG-specific personal phone | Remove — use contact lookup |
| `designer_phone_number` | TLG-specific | Move to company_settings |

### 5.2 Hardcoded Values to Move to Config

| Location | Current Value | Should Be |
|---|---|---|
| `services/outbound.py:137` | `f"TLG – Confirming..."` | `f"{sms_name} – Confirming..."` |
| `services/outbound.py:144` | `f"TLG – Final check..."` | `f"{sms_name} – Final check..."` |
| `services/outbound.py:150` | `f"TLG – Did you finish..."` | `f"{sms_name} – Did you finish..."` |
| `api/schedule.py:231` | `f"TLG – Schedule update..."` | `f"{sms_name} – Schedule update..."` |
| `webhooks/twilio.py:172` | `"TLG Homes job site status line"` | `"{company_name} job site status line"` |
| `webhooks/plivo.py` | `"job site status line"` | `"{company_name}"` (from settings) |
| `views/dashboard.py` | `"TLG Andon — Schedule updated..."` | `"{company_name} — Schedule updated..."` |
| `views/dashboard.py` | `"TLG Andon — Delegation..."` | `"{company_name} — Delegation..."` |

---

## 6. Architecture Improvements

### 6.1 Outbound Message Prefix Service

Create a service method that resolves the outbound SMS prefix from company settings:

```python
async def get_outbound_prefix(company_id: UUID) -> str:
    settings = await company_settings_repo.get(company_id)
    return settings.sms_display_name or settings.company_name or "Flow"
```

All outbound message functions should call this instead of using a hardcoded string.

### 6.2 Company-Aware HTTP Logging

The `Event.full_text.like("TLG –%")` pattern in `dashboard.py` (lines 406, 422) matches hardcoded prefix text to find previous outbound messages. This must be comparible with the configured `sms_display_name`. Either:
- Store the outbound prefix at send time alongside the event, or
- Compare against the configured prefix at query time

### 6.3 Template Title Block

The `base.html` template has `<title>{% block title %}TLG Andon{% endblock %}</title>`. Change to use a configurable app name:

```
<title>{% block title %}{{ app_name or 'Flow' }}{% endblock %}</title>
```

All child templates that set `{% block title %}... TLG Andon{% endblock %}` should use the app name variable.

### 6.4 Voice Prompt

The Plivo voice prompt in `webhooks/plivo.py` says "job site status line" — update to include company name from settings when available.

---

## 7. Technical Debt

### 7.1 Twilio Files Still Present

`webhooks/twilio.py` is still in the repository despite being deprecated. It contains hardcoded TLG references. Remove after confirming no production traffic routes to Twilio.

### 7.2 Old PRD.md at Root

`/root/pain-relief-app/PRD.md.bak` should be cleaned up.

### 7.3 Escalation-Related Files

- `templates/admin/escalations.html` — feature removed but file still present
- `templates/partials/escalation_banners.html` — feature removed but file still present
- Check if `escalation_config.json` is still referenced

---

## 8. Hardcoded Assumptions

| Assumption | Location | Impact |
|---|---|---|
| "TLG Homes" is the only company | Templates, seed data, env vars | Low for code, high for branding |
| Jimmy is the PM | `services/outbound.py` | Hardcoded name references |
| Clint is the foreman | Seed data, env vars | Hardcoded name references |
| 10 construction phases only | `TRADE_PHASES` in multiple files | May need custom phases per builder |
| Wisconsin/WI state | Default in onboarding | Should be configurable per tenant |
| USD currency | Analytics page | Fine for MVP |
| English only | All text | Fine for MVP |

---

## 9. Naming Improvements

### 9.1 High-Impact (User-Facing)

| Current | Recommended | Effort |
|---|---|---|
| "TLG Andon" in page titles | `{company_name} · Flow` | 1 hour |
| "TLG Andon — Daily View" | "Flow Dashboard" | 15 minutes |
| "TLG Andon — Schedule Updated" | `{company_name} — Schedule Updated` | 30 minutes |
| "Welcome to TLG Andon" | "Welcome to Flow" | 15 minutes |

### 9.2 Medium-Impact (Documentation)

Update all three source-of-truth documents to use "Flow Intelligence Platform" consistently.

### 9.3 Low-Impact (Internal Code — Defer)

| Current | Future | When |
|---|---|---|
| `andon_status` column | `flow_status` | Major DB migration |
| `events.outcome` field | `events.flow_grade` | Next schema version |
| `app/` directory | Keep | Never |
| `dashboard.py` route file | Keep | Never |

---

## 10. Low-Risk Quick Wins

These can be implemented immediately with minimal risk:

1. **`base.html` title block** — Change from "TLG Andon" to configurable `app_name`
2. **Dashboard title** — Already uses `{{ company_name }}` — just remove fallback "TLG" text
3. **All page titles** — Update 10+ template title blocks to use company_name variable
4. **Login page branding** — Remove hardcoded "TLG" icon/text, use company_name
5. **Seed data** — Add comment explaining TLG is Customer #1, not the platform
6. **Twilio voice prompt** — Update to use company_name from settings
7. **Delete stale files** — Remove escalation templates and old PRD backup

Estimated time: 2-3 hours for all quick wins.

---

## 11. High-Impact Future Improvements

| Improvement | Effort | Impact |
|---|---|---|
| Company Settings model (15+ fields) | 1 day | Enables true multi-tenant branding |
| Config-driven outbound SMS prefix | 4 hours | Cleans all hardcoded "TLG –" text |
| Seed data template-ization | 1 hour | Makes demo data generic |
| Plivo voice prompt per-company | 2 hours | Professional per-tenant voice greeting |
| Tenant-specific email templates | 1 day | Branded email notifications |
| Custom trade phases per builder | 2 days | Supports non-residential construction |

---

## 12. Recommended Order

### Sprint A (Quick Wins — 2-3 hours)
1. Update `base.html` title to use app_name variable
2. Update all page titles to use company_name/app_name
3. Remove hardcoded "TLG" icon from login page
4. Update seed data comments
5. Remove stale escalation files
6. Update dashboard.html header fallback text

### Sprint B (Branding — 1 day)
7. Expand tenant_settings with branding fields
8. Add company-aware outbound SMS prefix service
9. Update outbound.py, schedule.py messages
10. Update Plivo voice prompt
11. Rename user-facing "Andon" to "Flow" in templates
12. Update documentation (PRD, README, TECH_SPEC)

### Sprint C (Architecture — 2 days)
13. Add custom trade phases per builder
14. Deprecate TLG-specific env vars
15. Add company-aware query filters
16. Remove Twilio webhook file
17. Tenant-specific email templates
18. Multi-tenant analytics scoping
