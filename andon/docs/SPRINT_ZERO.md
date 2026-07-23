# Sprint Zero — Pilot Execution

**Start:** July 22, 2026
**Target:** July 31, 2026 (8 working days)
**Status:** Day 1 — Not Started

> Every task must answer: "Does this get the product into Jimmy's hands sooner?"

---

## Pilot Definition

One Builder. One PM. Twenty Houses. Real SMS. Real MMS. Real Voice. Real schedule recovery.

---

## Day 1 — SMS → Card

**Goal:** One SMS becomes one Issue Card.

| Item | Status | Verified |
|---|---|---|
| ☐ Configure Twilio webhook URL in console | ⬜ | ⬜ |
| ☐ Verify webhook receives POST from Twilio | ⬜ | ⬜ |
| ☐ Receive SMS → store raw message | ⬜ | ⬜ |
| ☐ Run keyword classifier on message | ⬜ | ⬜ |
| ☐ Create Issue Card (Yellow or Red) | ⬜ | ⬜ |
| ☐ Card appears on dashboard | ⬜ | ⬜ |
| ☐ Resolve card → card disappears | ⬜ | ⬜ |
| ☐ Verify audit log has the event | ⬜ | ⬜ |

**Definition of Done:** SMS → Card → Resolve works end-to-end.

**Actual completion:**

---

## Day 2 — MMS

**Goal:** Photo arrives on Issue Card.

| Item | Status | Verified |
|---|---|---|
| ☐ Receive image via MMS | ⬜ | ⬜ |
| ☐ Receive image + text caption | ⬜ | ⬜ |
| ☐ Store media permanently | ⬜ | ⬜ |
| ☐ Media attached to card | ⬜ | ⬜ |
| ☐ Gallery modal works | ⬜ | ⬜ |
| ☐ Classifier runs on caption text | ⬜ | ⬜ |

**Definition of Done:** Photo + caption → Card.

**Actual completion:**

---

## Day 3 — Voice

**Goal:** Voice → Transcript → Card.

| Item | Status | Verified |
|---|---|---|
| ☐ Receive incoming call | ⬜ | ⬜ |
| ☐ Play voicemail prompt | ⬜ | ⬜ |
| ☐ Record message | ⬜ | ⬜ |
| ☐ Receive recording callback | ⬜ | ⬜ |
| ☐ Download audio | ⬜ | ⬜ |
| ☐ Transcribe via Whisper | ⬜ | ⬜ |
| ☐ Card created from transcript | ⬜ | ⬜ |
| ☐ Audio playback available | ⬜ | ⬜ |

**Blocked by:** OPENAI_API_KEY

**Definition of Done:** Voice → Transcript → Card.

**Actual completion:**

---

## Day 4 — Scheduling Recovery

**Goal:** Jimmy can recover a schedule confidently.

| Item | Status | Verified |
|---|---|---|
| ☐ This Trade Only works | ⬜ | ⬜ |
| ☐ This Trade + Next Trade works | ⬜ | ⬜ |
| ☐ Cascade Selected Trades works | ⬜ | ⬜ |
| ☐ Review screen shows impact | ⬜ | ⬜ |
| ☐ Notifications sent | ⬜ | ⬜ |
| ☐ Schedule change audit recorded | ⬜ | ⬜ |

**Definition of Done:** Jimmy can fix a multi-trade delay faster than phone calls.

**Actual completion:**

---

## Day 5 — Role Play (One Complete House)

**Goal:** Run one house through all 10 trades with realistic delays.

| Phase | Delay Injected | Card Created? | Resolved? |
|---|---|---|---|
| Foundation / Concrete | ☐ | ☐ | ☐ |
| Framing | ☐ | ☐ | ☐ |
| Plumbing Rough | ☐ | ☐ | ☐ |
| HVAC Rough | ☐ | ☐ | ☐ |
| Electrical Rough | ☐ | ☐ | ☐ |
| Drywall / Plaster | ☐ | ☐ | ☐ |
| Paint | ☐ | ☐ | ☐ |
| Flooring | ☐ | ☐ | ☐ |
| Cabinets | ☐ | ☐ | ☐ |
| Finish Work | ☐ | ☐ | ☐ |

**Definition of Done:** No bugs found in the core loop.

**Actual completion:**

---

## Day 6 — Chaos Testing

**Goal:** System behaves predictably under edge cases.

| Test | Result |
|---|---|
| ☐ Duplicate SMS (same MessageSid resent) | ⬜ |
| ☐ Unknown sender (no matching contact) | ⬜ |
| ☐ Wrong address in message | ⬜ |
| ☐ Wrong trade mentioned | ⬜ |
| ☐ Typos and misspellings | ⬜ |
| ☐ Emoji in message | ⬜ |
| ☐ Empty body (MMS-only with no text) | ⬜ |
| ☐ Large MMS (5 photos) | ⬜ |
| ☐ Voice-only (no text caption) | ⬜ |
| ☐ Server restart during processing | ⬜ |
| ☐ Plivo/Twilio webhook timeout | ⬜ |

**Definition of Done:** All edge cases handled without crash.

**Actual completion:**

---

## Day 7 — Jimmy's Real Data

**Goal:** Twenty houses loaded and routing correctly.

| Item | Status |
|---|---|
| ☐ Import contacts from Jimmy's directory | ⬜ |
| ☐ Import projects (20 houses) | ⬜ |
| ☐ Import schedule with target dates | ⬜ |
| ☐ Verify SMS → correct project routing | ⬜ |
| ☐ Verify cards show correct data | ⬜ |
| ☐ Verify dashboard sorting (Red first, oldest first) | ⬜ |

**Definition of Done:** Jimmy's twenty houses are live.

**Actual completion:**

---

## Day 8 — Pilot Rehearsal

**Goal:** Run the platform exactly as Jimmy will. No coding unless critical.

| Item | Done |
|---|---|
| ☐ Founder acts as Jimmy for one full morning | ⬜ |
| ☐ Dashboard is first thing opened | ⬜ |
| ☐ SMS received and card appears | ⬜ |
| ☐ Issue resolved via dashboard | ⬜ |
| ☐ Schedule recovered via Date action | ⬜ |
| ☐ No critical bugs discovered | ⬜ |
| ☐ Pilot declared ready | ⬜ |

**Definition of Done:** Jimmy can start using the platform.

**Actual completion:**

---

## Current Blockers

| # | Blocker | Owner | Status | Needed From |
|---|---|---|---|---|
| 1 | Twilio webhook URL not set in console | You | ⏳ Pending | Messaging URL + Voice URL |
| 2 | OPENAI_API_KEY not set | You | ⏳ Pending | Add to `.env` |

---

## Next Action

**Configure Twilio webhook URL and provide OPENAI_API_KEY.**

After that: SMS → card in 30 minutes.
