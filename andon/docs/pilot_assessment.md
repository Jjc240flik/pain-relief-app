# Pilot MVP Assessment

**Date:** July 21, 2026
**Status:** Assessment Only — No Code Changes

---

## 1. Current Reality

### What's Actually Running

The **old pipeline** (`houses` + `schedule_items` + `events`) is the working system. This is what has real data:

| Resource | Old Pipeline | New Pipeline |
|---|---|---|
| Projects/Houses | 25 houses | 0 projects |
| Schedule entries | 153 schedule items | 0 trade schedule items |
| Events | 157 events | 0 inbound messages |
| Active cards | 1 (R/Y) | 0 |
| Plivo intake | ✅ Writing to events table | Route exists, no data |

The **new pipeline** (`projects` + `project_trades` + new models) has been scaffolded but is empty. No real projects, no contacts linked to projects, no trade schedule data.

### The Dashboard

The current dashboard queries the old `schedule_items` table for R/Y cards. It uses `houses` for address/city and `events` for messages/media. This is what Jimmy would see if he logged in today.

---

## 2. Pilot MVP Loop — Coverage Assessment

| Step | Required | Current State | Works? |
|---|---|---|---|
| 1. Project created | ✅ | 25 houses in old system. New project onboarding exists but is empty. | ⚠️ Old system has data. New system is scaffolded. |
| 2. Contacts assigned | ✅ | 15 contacts exist, assignable to houses. | ✅ |
| 3. Schedule entered | ✅ | 153 schedule items, all 10 trades covered across houses. | ✅ |
| 4a. SMS intake | ✅ | Plivo webhook → events table. Tested working. | ✅ |
| 4b. MMS (photos) | ✅ | Plivo webhook parses Media field. Gallery modal works. | ✅ |
| 4c. Voice intake | ⚠️ | Plivo webhook answers call + records. Transcription needs OPENAI_API_KEY. | ⚠️ Recording works, transcription disabled. |
| 5. Keyword classification | ✅ | Classifier v3 runs on inbound messages. | ✅ |
| 6. AI interpretation | ❌ | Not built. Deferred per pilot scope. | ✅ (Correct to defer) |
| 7. Card appears | ✅ | R/Y cards created in schedule_items. | ✅ |
| 8. Jimmy opens dashboard | ✅ | Dashboard at /dashboard. | ✅ |
| 9. Jimmy uses Resolve/Date/Call/Delegate | ✅ | All four actions exist and work. | ✅ |
| 10. Issue resolved | ✅ | Resolve sets status to Green. Card disappears. | ✅ |

### Verdict: 8.5/10 core loop steps are already functional.

The pilot loop works today with the old pipeline. The gaps are:
- **Voice transcription** — needs `OPENAI_API_KEY` in `.env`
- **New project onboarding** — exists but empty. Jimmy currently uses old houses.

---

## 3. What Jimmy Would See Today

If Jimmy logged in right now:

1. **Dashboard** → Loads. Shows existing R/Y cards from schedule_items.
2. **Cards** → Show trade, address, message, media, actions.
3. **Resolve** → Works. Card disappears.
4. **Date** → Opens date picker with cascade options.
5. **Call** → Shows dropdown with sub phone, boss phone, email.
6. **Delegate** → Opens modal with Boss/Office/Staff checkboxes. Sends SMS notification.
7. **New inbound SMS** → Plivo receives it, classifier grades it, card appears.

**What Jimmy cannot do today:**
- Create a new project through the new onboarding flow (old houses still work)
- Receive transcribed voice messages (OPENAI_API_KEY missing)
- See "Impact" or "Recommended Action" on cards (Flow Engine not built)

**What might confuse Jimmy:**
- Page titles say "TLG Andon" — should read "TLG Homes Flow"
- The "+" push button has a Send confirmation step (extra click)

---

## 4. Recommendations for 2-Week Pilot

### Must Do (Blocks the core loop)

| # | Item | Effort | Why |
|---|---|---|---|
| 1 | **Enable voice transcription** — Set `OPENAI_API_KEY` in `.env` | 5 min | Voice is a specified channel. Without it, voice messages show as untranscribed placeholders. |
| 2 | **Fix page titles** — Replace "TLG Andon" → "TLG Homes Flow" or configurable | 1 hr | Branding confusion. Jimmy shouldn't see "TLG Andon." |
| 3 | **Fix Push button** — Remove Send confirmation. Push is immediate. | 30 min | Current flow adds an extra click. |

### Should Do (Improves daily usability)

| # | Item | Effort | Why |
|---|---|---|---|
| 4 | **Seed a real project** — Create one project via the new onboarding with Jimmy's first house | 15 min | Validates the new onboarding path with real data. |
| 5 | **Add Projects link to dashboard nav** — Already exists. Verify it works. | 15 min | Navigation consistency. |
| 6 | **Verify SMS→Card latency** — SMS should produce a card in under 5 seconds | 30 min | Jimmy needs to trust the system is live. |

### Could Do (Nice to have)

| # | Item | Effort | Why |
|---|---|---|---|
| 7 | **Add "Impact" to card template** — Currently cards show raw message. Flow Engine not built, but a simple statement like "Next trade: Plumbing" could be added from schedule context. | 2 hr | Helps Jimmy understand *why* the card matters. |
| 8 | **Document the Plivo webhook URLs** for Jimmy's reference | 1 hr | He needs to configure Plivo dashboard. |

### Defer (Not needed for pilot)

| # | Item | Why |
|---|---|---|
| — | Data migration (houses → projects) | Old system works. Run both in parallel. |
| — | Flow Engine build | Not needed to prove daily usage. |
| — | AI interpreter | Keyword classifier handles 90%+ of messages. |
| — | Multi-tenancy | Single builder for pilot. |
| — | New database tables | Old tables have the data. |
| — | Dashboard simplification | Spec says don't remove actions. |

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Plivo webhook goes down | Low | High | Server is running. Monitor health endpoint. |
| Classifier misclassifies | Medium | Medium | Delegate + Feedback override work. Jimmy can correct. |
| Voice messages not transcribed | High | Low | Audio is stored. Transcription can be added later. Set OPENAI_API_KEY. |
| Jimmy doesn't use it | Medium | High | This is what we're testing. Daily usage is the success metric. |
| Old pipeline breaks during changes | Low | High | Don't touch old pipeline. Only add. |
| New project onboarding confusing | Medium | Low | Don't force Jimmy to use it. Old houses still work. |

---

## 6. Pilot Success Check

After two weeks, the pilot succeeds if:

> **Jimmy opens the dashboard before making his first round of phone calls each morning.**

Secondary signals:
- Jimmy uses Resolve/Date/Call/Delegate instead of phone calls
- Jimmy corrects classification (👎) when the system is wrong
- Jimmy creates at least one new project through the onboarding flow
- Jimmy reports catching at least one issue earlier than before

---

## 7. Implementation Plan for Next 2 Weeks

### Week 1 — Stabilize
1. Set `OPENAI_API_KEY` → voice transcription works
2. Fix page titles → branding consistent
3. Fix Push button → immediate push, no confirmation
4. Verify SMS→Card pipeline end-to-end with Jimmy's Plivo number
5. Create one real project via new onboarding

### Week 2 — Validate
6. Jimmy uses the system for daily operations
7. Collect feedback on dashboard, actions, classification
8. Fix any issues Jimmy reports within 24 hours
9. Measure daily usage
10. Decide: continue pilot or adjust scope

---

## 8. Current Verdict

**The Pilot MVP core loop is 80% functional today.**

The highest-impact action is enabling voice transcription (OPENAI_API_KEY) and fixing the page titles. Everything else — project onboarding, contact management, SMS intake, classification, dashboard, actions — is already working through the old pipeline.

The new architecture (projects, trade_schedule_items, inbound_messages, etc.) should remain in place as the long-term target but should NOT be migrated to until the pilot validates daily usage.
