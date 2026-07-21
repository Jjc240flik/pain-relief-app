# Product Maturity Roadmap: Flow Intelligence Platform

**Date:** July 21, 2026
**Author:** Lead Architect
**Purpose:** Describe how the platform evolves from MVP prototype to multi-industry operational intelligence layer.

This is not a feature roadmap.

It is a product maturity roadmap.

Each stage represents a qualitative leap in what the platform can do, who it serves, and how it fits into the construction ecosystem.

---

## Stage 1 — Prototype Validation

**Status:** Current (MVP pilot)

**Goal:** Prove that builders trust the system enough to open it every morning.

This stage is not about scale, features, or performance. It is about one question:

> Does the superintendent check the dashboard before leaving the house?

### Focus Areas

- **SMS intake** — Subcontractors can text an issue and a card appears.
- **Keyword classification** — The system correctly identifies R/Y/G from common construction language.
- **Manual scheduling** — Projects have basic dates. Cards appear for issues.
- **Simple dashboard** — Yellow and Red cards only. Sorted by age. Four actions.
- **Early interviews** — Direct feedback from Jimmy and Clint. What works? What's confusing? What's missing?
- **Single pilot builder** — TLG Homes (The Lodal Group) as Customer #1.

### What the Platform Can Do

- Receive an SMS, classify it, create a card.
- PM can Resolve, Date, Call, or Delegate.
- Cards persist until resolved.
- Basic outbound check-ins.

### What the Platform Cannot Do Yet

- Interpret free-form language (AI).
- Understand schedule dependencies.
- Support multiple builders.
- Integrate with other tools.

### Success Criteria

- [ ] Daily use without reminders.
- [ ] Reduced phone calls between PM and subs.
- [ ] At least one issue detected earlier than the phone-and-memory process.
- [ ] PM can onboard a project in under five minutes.
- [ ] Feedback loop: PM corrects the system, system improves.

### Duration

2–3 months of active pilot use.

### Exit Criteria

The pilot builder opens the dashboard first every morning.

---

## Stage 2 — Flow Intelligence

**Goal:** Move from issue tracking to operational awareness.

The platform stops being a "message → card" pipeline and becomes a "message → context → impact → action" engine.

### Focus Areas

- **Project onboarding** — Full project creation with estimated and target dates.
- **Contact management** — Per-project contacts with roles and notification routing.
- **Date authority** — The system understands the difference between estimated, target, and confirmed dates.
- **AI interpretation** — Free-form messages are parsed into structured events.
- **Flow Engine** — Deterministic rules evaluate production impact based on schedule maturity.
- **Language Grade + Flow Grade** — Two independent grading layers preserved in the audit log.
- **Improved dashboard** — Cards show impact summary and recommended action, not just the raw message.
- **Manager override** — PM can correct the system. All overrides are logged.

### What the Platform Can Do (New)

- Distinguish "cannot start tomorrow" from "might be delayed next week."
- Know whether a delay blocks another trade.
- Show the PM *why* a card is Red or Yellow.
- Remember every grading decision permanently.
- Accept corrections and learn from them.

### What the Platform Cannot Do Yet

- Integrate with external scheduling tools.
- Support multiple builders on one instance.
- Handle voice, email, or photo intake.

### Success Criteria

- [ ] PM trusts the Flow Engine grade over their own first impression.
- [ ] Fewer production surprises (crews arrive to find the previous trade not done).
- [ ] Dashboard is the first thing the PM checks every morning.
- [ ] PM uses Date action to reschedule trades instead of calling subs.

### Duration

3–4 months after Stage 1 exit.

### Risk

The Flow Engine may initially produce lower-quality grades than the existing keyword classifier for certain message types. This is expected. The two-grade system (Language Grade + Flow Grade) allows comparison. Run both in parallel. Let the better one win until the Flow Engine catches up.

---

## Stage 3 — Operational Platform

**Goal:** Integrate with existing builder workflows so the platform becomes invisible.

The platform should not require the builder to change how they work. It adapts to their existing tools.

### Focus Areas

- **Voice intake** — Voicemail transcription via Whisper. Subs call in issues.
- **Photo/MMS intake** — Subs text photos. Images appear on the card.
- **Email intake** — SendGrid Inbound Parse. Subs email issues.
- **Calendar integration** — Google Calendar / Microsoft 365. Schedule changes sync automatically.
- **Public REST API** — Everything the dashboard can do, the API can do.
- **Zapier connector** — Non-technical builders wire Flow into their existing toolchain.
- **Buildertrend / Procore / JobTread integrations** — Bi-directional schedule sync.
- **Analytics** — Usage trends, classification accuracy, resolution times, cost tracking.

### What the Platform Can Do (New)

- Receive issues through any channel the sub prefers.
- Sync schedules with the builder's system of record.
- Push updates back to the builder's project management tool.
- Report on its own performance.

### What the Platform Cannot Do Yet

- Support multiple tenants with isolated data.
- Handle enterprise security requirements.
- Bill customers.
- Self-serve onboarding.

### Success Criteria

- [ ] Subs use their preferred channel without being reminded how.
- [ ] The PM never manually enters a schedule — it syncs from Buildertrend.
- [ ] No duplicate entry between Flow and the builder's primary system.
- [ ] Integration setup takes under an hour.

### Duration

4–6 months after Stage 2 exit.

---

## Stage 4 — Commercial SaaS

**Goal:** Support many builders on a single, secure, scalable platform.

The architecture shifts from single-tenant to multi-tenant. Company branding, user roles, billing, and self-service onboarding become requirements.

### Focus Areas

- **Multi-tenancy** — Complete data isolation between builders.
- **Company branding** — Configurable logo, colors, SMS display name, email signature.
- **User roles & permissions** — Admin, PM, Superintendent, Office, Read-only.
- **Billing & subscriptions** — Usage-based or per-project pricing.
- **Self-service onboarding** — Builders sign up, add their company info, invite their team.
- **Enterprise security** — Audit logging, SSO, encryption at rest, SOC 2 preparation.
- **Performance** — Query optimization, connection pooling, caching, CDN for media.
- **Monitoring & alerting** — Proactive detection of webhook failures, classification degradation, integration outages.
- **Customer success tools** — Admin panel for support team, impersonation, tenant configuration.

### What the Platform Can Do (New)

- Any builder signs up and starts using Flow within minutes.
- Each builder sees their own branding.
- The platform operator can monitor all tenants from one dashboard.
- Billing is automated.

### What the Platform Cannot Do Yet

- Operate outside residential construction.
- Handle non-construction workflows.

### Success Criteria

- [ ] Self-service signup → project creation → first card in under 10 minutes.
- [ ] Zero data leakage between tenants.
- [ ] < 99.9% uptime SLA.
- [ ] Support team can diagnose tenant issues without code access.
- [ ] First 10 paying customers on the platform.

### Duration

6–9 months after Stage 3 exit.

---

## Stage 5 — Flow Intelligence Platform (Multi-Industry)

**Goal:** Expand beyond residential construction into any industry where operational flow matters.

The core philosophy — *reduce uncertainty, not store information* — is not construction-specific. It applies to any operation where:

- Multiple parties contribute to a workflow.
- Delays in one step block downstream work.
- A manager needs to know "what needs my attention right now."
- Communication happens through informal channels (text, call, photo, email).

### Target Industries

| Industry | Why Flow Applies |
|---|---|
| **Commercial Construction** | Same problem as residential: subs, schedules, inspections, blockers. Larger projects, more trades, higher stakes. The Flow Engine's schedule maturity model maps directly. |
| **Manufacturing** | Production lines have dependencies. A machine breakdown, material shortage, or quality issue blocks downstream stations. Flow becomes a production-line Andon. The channel shifts from SMS to sensors + manual reports. |
| **Service Companies** | HVAC, plumbing, electrical service companies dispatch technicians. A delayed technician blocks the next job. Flow tracks "which jobs are Red/Yellow today." Inputs come from dispatch software + tech check-ins. |
| **Utilities / Field Operations** | Crews maintain infrastructure. A crew that cannot access a site, a missing permit, or a weather delay blocks the work. Flow surfaces the exception. Inputs come from GPS check-ins + manual reports. |
| **Facilities Management** | Maintenance requests, vendor coordination, access issues. A delayed vendor means the building isn't ready for occupancy. Same pattern: uncertainty needs reduction. |
| **Production Operations** | Film/TV production, event production, theatrical production. Dozens of vendors, tight schedules, constant blockers. A missing prop, delayed lighting crew, or weather issue blocks the next scene. The same flow engine applies. |
| **Logistics / Supply Chain** | A delayed supplier, customs hold, or transport breakdown blocks downstream delivery. Flow tracks exceptions. Inputs come from tracking systems + manual reports. |

### Why the Architecture Transfers

The platform's core abstractions are industry-agnostic:

- **Inbound message** → Any channel, any format.
- **Construction event** → Replace with "operational event." The schema (event_type, trade, summary, certainty) is generic.
- **Schedule maturity** → Any workflow with estimated/target/confirmed dates.
- **Flow Grade** → Deterministic rules about blocked production, critical path, downstream impact.
- **Issue card** → "What needs my attention" — universal.
- **Resolve / Date / Call / Delegate** → Universal actions.

Changes required per industry:
- **Trade list** — Configurable per tenant. Residential: 10 trades. Manufacturing: production stations. Service: technician types.
- **Flow rules** — Industry-specific rulesets (e.g., "inspection failure" in construction → "quality hold" in manufacturing).
- **Channels** — Sensors and API integrations become more important than SMS.
- **Terminology** — "Project" → "Work order" → "Production run" → "Event."

### What the Platform Can Do (New)

- Operate in any industry with flow-based operations.
- Custom trade/phases per tenant.
- Industry-specific flow rule packs.
- Multi-channel intake including API/ sensor integrations.

### Success Criteria

- [ ] At least one non-construction customer in production.
- [ ] Industry-specific rule packs available as add-ons.
- [ ] Platform revenue diversified beyond residential construction.

### Duration

12–18 months after Stage 4 exit.

---

## Evolution Summary

```
Stage 1             Stage 2             Stage 3             Stage 4             Stage 5
Prototype           Flow Intelligence   Operational         Commercial SaaS     Platform
                    Platform
                                                                              
Single builder      Single builder      Single builder      Many builders       Many industries
SMS only            SMS + manual        All channels        Multi-tenant        Custom configs
Keyword engine      AI + Flow Engine    Integration-ready   Enterprise-ready    Industry packs
Manual schedule     Date authority      Schedule sync       Billing             API-first
Basic dashboard     Impact-aware        API + Zapier        Self-service        Multi-channel
                    cards                                   Security            
```

## Guiding Principle for All Stages

Each stage must answer the question:

> Does this make the superintendent's morning faster?

If yes → Build it.
If no → Question it.
If uncertain → Ask the superintendent.
