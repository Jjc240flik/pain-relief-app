# Pilot Execution Checklist

**Document Purpose:** Single source of truth for the Pilot Sprint.
**Last Updated:** July 21, 2026
**Status:** Phase 1 In Progress

> The goal is not to build the complete Flow Intelligence Platform.
> The goal is to prove that one superintendent can manage multiple active homes more effectively using this product than through phone calls, memory, and spreadsheets.

---

## Development Principles

These principles override feature development during the pilot.

1. **Do not surprise the founder with large architectural changes.** Report proposed architectural changes first. Wait for approval before implementing them.

2. **Implement only the agreed scope.** Do not expand features unless required for the pilot.

3. **Every coding decision must answer one question:** "Does this get the product into Jimmy's hands sooner without sacrificing reliability?" If YES → Do it. If NO → Defer it until after the pilot.

4. **Reliability is more important than cleverness.**

5. **A working feature always beats a perfect feature.**

6. **Jimmy is the Product Manager.** Real-world feedback overrides assumptions.

---

## Phase 1 — Plivo Foundation

**Status:** In Progress

| Item | Status | Notes |
|---|---|---|
| ☐ Complete Plivo implementation audit | ✅ Done | `docs/plivo_audit.md` |
| ☐ Configure Plivo account | ❌ Blocked | Requires user to sign up at console.plivo.com |
| ☐ Configure phone number | ❌ Blocked | Requires user to purchase SMS+MMS+Voice number |
| ☐ Configure environment variables | ⬜ | PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_PHONE_NUMBER, OPENAI_API_KEY |
| ☐ Configure inbound SMS webhook | ⬜ | After credentials — set Plivo Message URL |
| ☐ Configure outbound SMS | ⬜ | Code exists, needs credentials |
| ☐ Configure delivery callbacks | ⬜ | New route needed |
| ☐ Verify webhook security | ⬜ | Add signature validation |
| ☐ Verify duplicate protection | ⬜ | Add MessageUUID dedup |
| ☐ Verify SMS end-to-end | ⬜ | Requires all above |

**Current Blocker:** Missing Plivo credentials + OpenAI API key. See `docs/plivo_audit.md` for details.

---

## Phase 2 — Media (MMS + Voice)

**Status:** Not Started

| Item | Status | Notes |
|---|---|---|
| ☐ Configure MMS | ⬜ | |
| ☐ Receive images | ⬜ | Code handles Plivo Media field |
| ☐ Store images to persistent storage | ⬜ | Currently stores Plivo URL only — need download |
| ☐ Display images on card | ⬜ | Gallery modal exists, needs verified |
| ☐ Verify MMS → Card pipeline | ⬜ | |
| ☐ Configure Voice / voicemail | ⬜ | Plivo XML response works |
| ☐ Configure recording callback | ⬜ | Route exists |
| ☐ Store recordings | ⬜ | Need to download audio |
| ☐ Whisper transcription | ❌ Blocked | Requires OPENAI_API_KEY |
| ☐ Verify Voice → Card pipeline | ⬜ | |

---

## Phase 3 — First Real Project

**Status:** Not Started

| Item | Status | Notes |
|---|---|---|
| ☐ Create first project via onboarding | ⬜ | |
| ☐ Add contacts to project | ⬜ | |
| ☐ Add schedule (target dates sufficient) | ⬜ | |
| ☐ Verify dashboard shows correct data | ⬜ | |
| ☐ Send first real SMS from known sub | ⬜ | Requires Plivo |
| ☐ Generate first Yellow card from SMS | ⬜ | |
| ☐ Generate first Red card from SMS | ⬜ | |
| ☐ Resolve first issue via dashboard | ⬜ | |
| ☐ Date change works on a card | ⬜ | |
| ☐ Call sub from card | ⬜ | |
| ☐ Delegate an issue | ⬜ | |

---

## Phase 4 — Multi-Project Test

**Status:** Not Started

| Item | Status | Notes |
|---|---|---|
| ☐ Add three houses as projects | ⬜ | |
| ☐ Verify scheduling across projects | ⬜ | |
| ☐ Verify multiple trades per project | ⬜ | |
| ☐ Verify notifications to correct contacts | ⬜ | |
| ☐ Verify dashboard sorting (Red before Yellow, oldest first) | ⬜ | |
| ☐ Verify latency (SMS→card under 5s) | ⬜ | |

---

## Phase 5 — Jimmy Pilot

**Status:** Not Started

| Item | Status | Notes |
|---|---|---|
| ☐ Jimmy onboarded (user account created) | ⬜ | |
| ☐ Dashboard walkthrough with Jimmy | ⬜ | |
| ☐ First live issue detected via SMS | ⬜ | |
| ☐ First live resolution via dashboard | ⬜ | |
| ☐ Daily usage begins | ⬜ | |
| ☐ Morning Dashboard First metric tracking | ⬜ | Code in place, needs data |
| ☐ Pilot Health dashboard visible to founder | ✅ Done | `/admin/analytics` |
| ☐ Founder analytics operational | ✅ Done | Existing analytics + Pilot Health |

---

## Pilot Success Metrics

Track these throughout the pilot.

| Metric | Current | Target |
|---|---|---|
| Daily Active PM | — | Every weekday |
| Morning Dashboard First | — | Yes |
| Issues Detected | — | Meaningful issues caught early |
| Issues Resolved | — | > 80% resolution rate |
| Resolution Rate | — | > 80% |
| Average Resolution Time | — | < 4 hours |
| Classifier Accuracy | — | > 90% |
| SMS Health | — | 100% delivery |
| MMS Health | — | Photos visible on cards |
| Voice Health | — | Transcripts readable |

---

## Current Blockers

| # | Description | Priority | Owner | Status | Expected Resolution |
|---|---|---|---|---|---|
| 1 | Plivo credentials missing (AUTH_ID, AUTH_TOKEN, PHONE_NUMBER) | Critical | User | ⏳ Pending | TBD |
| 2 | OpenAI API key missing (voice transcription) | High | User | ⏳ Pending | TBD |
| 3 | No Plivo account or phone number purchased | Critical | User | ⏳ Pending | TBD |

No code blockers exist. Credentials are the only gating factor.

---

## Current Sprint

| Field | Value |
|---|---|
| **Current Objective** | Complete Plivo Foundation (Phase 1) so Jimmy can receive SMS → cards |
| **Expected Completion** | TBD — blocked on credentials |

---

## Next Action

> **Configure Plivo account and provide credentials.**
>
> 1. Sign up at https://console.plivo.com
> 2. Purchase a phone number with SMS + MMS + Voice
> 3. Add PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_PHONE_NUMBER to `.env`
> 4. Add OPENAI_API_KEY to `.env`

After credentials are set: I will add signature validation, dedup, and verify end-to-end SMS within 1 hour.

---

## Completed Milestones

| Date | Milestone | Verified |
|---|---|---|
| Jul 21 | Plivo webhooks accept POST and respond 200 | ✅ |
| Jul 21 | Keyword classifier grades inbound messages | ✅ |
| Jul 21 | Outbound supports Plivo provider in code | ✅ (log mode) |
| Jul 21 | Voice webhook returns valid Plivo XML | ✅ |
| Jul 21 | MMS media URLs extracted from Plivo payload | ✅ |
| Jul 21 | Pilot Health dashboard deployed | ✅ |
| Jul 21 | User activity tracking (login, dashboard, actions) | ✅ |

---

## Maintenance Notes

Update this document whenever:
- A milestone is completed
- A blocker appears or is resolved
- Scope changes
- A task is deferred
- Pilot readiness changes

This document should always accurately reflect the current state of development.
