# Dashboard Action Review

**Date:** July 21, 2026
**Author:** Lead Architect
**Purpose:** Evaluate every existing dashboard action against the Flow Intelligence Platform philosophy.

---

## Review Framework

Each action is evaluated against one question:

> Does this action reduce work for the superintendent?

If yes → Keep or Modify.
If no → Remove, with a replacement workflow.

Additional considerations:
- Does it reduce uncertainty?
- Does it remove a phone call, site visit, or decision?
- Does it create work instead of removing it?
- Does it belong on the daily attention dashboard or in an admin panel?

---

## Action Inventory

### 1. Resolve

| Field | Value |
|---|---|
| **Current Purpose** | Sets card status to Green. Card disappears from the daily view. Logs resolution time. |
| **User Problem It Solves** | PM marks an issue as handled. Prevents the same card from lingering. Provides closure. |
| **Aligns with Philosophy?** | Yes. Management by exception — resolved issues disappear automatically. |
| **Decision** | **Keep** |
| **Justification** | Foundational action. Every PM needs to close out a completed issue. Removing it would trap cards on the dashboard forever. |
| **Replacement Workflow** | N/A |
| **Complexity** | Trivial — already exists |

---

### 2. Date

| Field | Value |
|---|---|
| **Current Purpose** | Opens a date picker with cascade options: this trade only, + next trade, or selected trades with per-trade dates. Also includes a Notify section (Boss/Office/Staff). |
| **User Problem It Solves** | PM needs to reschedule a trade without calling the sub. The cascade options let them shift downstream trades in one action instead of editing each one. |
| **Aligns with Philosophy?** | Yes. Reduces phone calls. Reduces manual schedule edits. |
| **Decision** | **Keep** (modify scope) |
| **Justification** | The Date action is one of the four specified actions. However, the "Notify Boss/Office/Staff" section inside the date modal is redundant with Delegate. Notifications on date changes should be handled by the notification service automatically, not as a checkbox in the date picker. |
| **Replacement Workflow** | Remove the manual Notify checkboxes from the Date modal. Notifications for schedule changes are triggered automatically by the Flow Engine when a confirmed or target date is moved. |
| **Complexity** | Low — remove inline notify section, keep cascade + per-trade dates |

---

### 3. Call

| Field | Value |
|---|---|
| **Current Purpose** | Drops down a menu with: Call Sub, Call Boss, Email Sub. Each option opens the relevant tel:/mailto: link. |
| **User Problem It Solves** | PM needs to contact the sub or boss immediately. One click opens the dialer. Removes the need to look up the phone number. |
| **Aligns with Philosophy?** | Yes. Reduces work. Removes a lookup step. |
| **Decision** | **Keep** |
| **Justification** | One of the four specified actions. The dropdown with sub/boss/email options is useful and doesn't add clutter. Keep as-is. |
| **Replacement Workflow** | N/A |
| **Complexity** | None |

---

### 4. Delegate

| Field | Value |
|---|---|
| **Current Purpose** | Opens a modal with Boss/Office/Staff checkboxes. Selecting one or more sends an SMS notification and logs the delegation. |
| **User Problem It Solves** | PM needs to notify someone else about an issue. Instead of calling or texting separately, they click Delegate and the system sends the notification. |
| **Aligns with Philosophy?** | Yes. Reduces a phone call or separate text message. |
| **Decision** | **Keep** (modify scope) |
| **Justification** | Delegation is one of the four specified actions. The current implementation is close to correct. However, the Boss/Office/Staff checkboxes are better placed as a persistent notification preference per project contact, not as an ad-hoc selection every time. Consider remembering the last selection per project or using default roles. |
| **Replacement Workflow** | Add default delegation routing per project (e.g., "Framing issues → delegate to Framing foreman"). The PM can still override per-action. |
| **Complexity** | Medium — current modal needs minor UX polish but is functional |

---

### 5. Push +1 Day

| Field | Value |
|---|---|
| **Current Purpose** | Clicking the **+** button increments a counter (shows +1, +2, +3). A **Send** button appears to confirm. Pushes the schedule for that trade by N days. |
| **User Problem It Solves** | PM needs to delay a trade by a few days. Instead of opening the Date picker and setting a specific date, they can click + repeatedly and confirm. |
| **Aligns with Philosophy?** | Partially. It removes work (quick push without date picker), but the current UX (counter + Send button) adds a confirmation step that didn't exist before. |
| **Decision** | **Modify** |
| **Justification** | The spec lists four actions: Resolve, Date, Call, Delegate. Push is not one of them. However, the *need* it solves is real: "I need this trade to start later by a few days." The Date action already solves this — the PM enters a new date. The +1 Day button is a faster way to do the same thing. Keep it if it removes work. The current Send-button confirmation flow adds a click — consider making it immediate again (click = push 1 day, label updates to show total pushed). |
| **Replacement Workflow** | Keep as a fast-path alternative to the Date picker. Make push immediate (no Send confirmation). Label shows +N. After each push, the card updates silently. |
| **Complexity** | Low — revert to immediate push, keep cumulative counter display |

---

### 6. Push +3 Days

| Field | Value |
|---|---|
| **Current Purpose** | Pushes schedule by 3 days in one click. Was removed in a previous cleanup. |
| **User Problem It Solves** | Pushing by 3 in one click is faster than clicking + three times. |
| **Aligns with Philosophy?** | Partially. Same argument as +1 Day. The + button can be clicked multiple times — a separate +3 button is redundant. |
| **Decision** | **Remove** (already removed) |
| **Justification** | Already removed. The + button with cumulative counter replaces this. Clicking + three times achieves the same result with the same number of clicks (3) while being more flexible (can push by 1, 2, 3, 4, etc.). |
| **Replacement Workflow** | Use + button with cumulative counter. Click N times, then Send (or immediate). |
| **Complexity** | None — already removed |

---

### 7. Push Send Confirmation

| Field | Value |
|---|---|
| **Current Purpose** | After clicking + to set a cumulative count, a green **Send** button appears. Clicking Send commits the push. |
| **User Problem It Solves** | Prevents accidental pushes. PM can build up a count like +5 and then confirm. |
| **Aligns with Philosophy?** | No. It adds a click. The superintendent is not worried about accidentally pushing by 1 day — that's trivially reversible. The Send button creates work (an extra confirmation) without removing work. |
| **Decision** | **Remove** |
| **Justification** | The Send confirmation adds friction without preventing a meaningful mistake. Pushing by +1 is harmless. Pushing by +7 in error is unlikely. If it happens, the Date action can correct it. Remove the Send button. Make the + button push immediately on each click. |
| **Replacement Workflow** | Click + → immediately pushes +1 day. Button label shows +N cumulative for the session. Card updates silently. No confirmation needed. |
| **Complexity** | Low — remove Send button logic, keep immediate push |

---

### 8. Contextual Quick Actions (Check Truss Specs, Call Supplier, etc.)

| Field | Value |
|---|---|
| **Current Purpose** | Shows trade-specific quick-action buttons below the main action row. For Framing: "Check Truss Specs", "Call Supplier", "Request Inspection". These pre-fill the delegation note or open the dialer. |
| **User Problem It Solves** | New superintendents may not know the standard response for a framing issue. The quick actions guide them: "If this is a truss issue, click here to pre-fill the delegation note." |
| **Aligns with Philosophy?** | No. For an experienced superintendent, these buttons are noise. The "Check Truss Specs" action pre-fills a note that says "Verify truss specifications..." — the PM still has to delegate it. It doesn't remove work, it just pre-fills a text field. The "Call Supplier" button duplicates the existing Call dropdown. |
| **Decision** | **Remove** from daily dashboard |
| **Justification** | These buttons add visual clutter below the main action row. They duplicate functionality (Call) or create work (pre-fill a note that still needs to be sent). An experienced PM doesn't need a button to tell them to check truss specs. If this guidance is valuable, move it to an onboarding/training context, not the daily dashboard. |
| **Replacement Workflow** | Remove the contextual action row. The Call dropdown already includes "Call Supplier" when a sub phone is available. The Date action handles rescheduling. The PM does not need trade-specific hints on every card. |
| **Complexity** | Low — remove template section and backend context building |

---

### 9. Feedback Widget (👍 / 👎 + Status Correction)

| Field | Value |
|---|---|
| **Current Purpose** | PM confirms (👍) or corrects (👎) the card's classification. 👎 opens a picker to select R/Y/G and optionally add a comment. |
| **User Problem It Solves** | The classifier sometimes gets the status wrong. The PM corrects it. The correction is logged and feeds back into the classifier. |
| **Aligns with Philosophy?** | Yes. The spec's grading model explicitly preserves Manager Override. The PM must be able to correct the system. |
| **Decision** | **Keep** (move placement) |
| **Justification** | The Feedback/Override action is explicitly required by the PRD (Section 10.5: Manager Override). It's essential for building trust — if the system gets it wrong and the PM can't fix it, they'll stop trusting the cards. However, the current placement at the bottom of every card may be too prominent. Consider moving it to a secondary position (collapsed or under a "⋯" menu) since corrections are the exception, not the rule. |
| **Replacement Workflow** | Keep the functionality. Move to a subtle "⋯" overflow menu or reduce visual weight. The 👍 can be a single-click confirm. The 👎 should still show the status picker + comment. |
| **Complexity** | Low — move UI elements, keep backend logic |

---

### 10. Media Viewer (Photo Gallery + Video Playback)

| Field | Value |
|---|---|
| **Current Purpose** | When an SMS includes photos or videos, the card shows "📷 N photos" and "▶️ Video" buttons. Clicking opens a modal gallery or video player. |
| **User Problem It Solves** | PM can see the issue without visiting the site. A photo of a cracked foundation or unsealed ductwork communicates more than a text message. |
| **Aligns with Philosophy?** | Yes. Reduces site visits. Reduces uncertainty. |
| **Decision** | **Keep** |
| **Justification** | Media is a core part of the intake pipeline (PRD Section 8). Viewing a photo of the issue can save a 30-minute site visit. This directly supports the philosophy of reducing work. |
| **Replacement Workflow** | N/A |
| **Complexity** | None |

---

### 11. Voice Playback / Transcription

| Field | Value |
|---|---|
| **Current Purpose** | Voice messages are transcribed via Whisper. The transcription text appears in the card. If the audio file is stored, it could be played back. |
| **User Problem It Solves** | Sub can call in an issue instead of texting. The PM reads the transcription. |
| **Aligns with Philosophy?** | Yes. Low-effort input for the sub. The PM reads the result. |
| **Decision** | **Keep** |
| **Justification** | Voice is a specified inbound channel (PRD Section 8). The transcription pipeline is correct. Playback should be available when audio is stored. |
| **Replacement Workflow** | N/A |
| **Complexity** | None |

---

### 12. Red/Yellow Filter Badges

| Field | Value |
|---|---|
| **Current Purpose** | Clicking the Red or Yellow count badge in the header filters the card list to show only that status. Refresh resets to all. |
| **User Problem It Solves** | PM wants to focus only on Red issues (blocked production) or only on Yellow issues (needs attention). |
| **Aligns with Philosophy?** | Yes. Management by exception — let the PM focus on the most critical items. |
| **Decision** | **Keep** |
| **Justification** | Sorting Red before Yellow already helps, but filtering to "only Red" lets the PM triage faster. Low complexity, high utility. |
| **Replacement Workflow** | N/A |
| **Complexity** | None |

---

### 13. Auto-Refresh (60-second interval)

| Field | Value |
|---|---|
| **Current Purpose** | The card list auto-refreshes every 60 seconds via HTMX. |
| **User Problem It Solves** | PM doesn't need to manually refresh to see new cards. New issues appear automatically. |
| **Aligns with Philosophy?** | Yes. Reduces work. Removes the need to hit refresh. |
| **Decision** | **Keep** |
| **Justification** | Auto-refresh is invisible when nothing changes and valuable when a new card appears. Keep at 60s. |
| **Replacement Workflow** | N/A |
| **Complexity** | None |

---

### 14. Escalation Banner (top-of-page alerts)

| Field | Value |
|---|---|
| **Current Purpose** | Previously showed a red banner for "3 Red issues on same house." Has been removed. |
| **User Problem It Solves** | Alerted the PM when multiple Red issues occurred on one house. |
| **Aligns with Philosophy?** | No. The card list already shows all Red issues sorted by age. A banner duplicates that information and adds visual noise. The Flow Engine should handle escalation logic, not a separate banner system. |
| **Decision** | **Remove** (already removed) |
| **Justification** | Already removed. The card list is sufficient. |
| **Replacement Workflow** | Let the Flow Engine determine severity. Cards sorted by age with Red first is sufficient. |
| **Complexity** | None — already removed |

---

### 15. Delegate Status Buttons (In Progress / Resolved / Reclaim)

| Field | Value |
|---|---|
| **Current Purpose** | After delegating, the card shows "▶ In Progress" and "✓ Resolved" buttons for the assignee to update status. |
| **User Problem It Solves** | The person assigned to the issue can mark it as in progress or resolved without calling the PM. |
| **Aligns with Philosophy?** | Yes. Reduces a phone call or text message. The assignee updates the status directly. |
| **Decision** | **Keep** |
| **Justification** | This reduces work for both the PM and the assignee. Without it, the assignee would need to text or call the PM to say "I'm working on it" or "It's done." The buttons are conditional (only appear when delegated) so they don't add clutter to every card. |
| **Replacement Workflow** | N/A |
| **Complexity** | None |

---

## Summary Table

| Action | Decision | Justification |
|---|---|---|
| Resolve | ✅ Keep | Foundational. Cards must close. |
| Date | ✅ Keep (modify) | Remove inline Notify checkboxes. Notifications are automatic. |
| Call | ✅ Keep | One of four specified actions. Reduces lookup work. |
| Delegate | ✅ Keep (modify) | Default routing per project, override per action. |
| Push +1 Day | ⚠️ Modify | Keep as fast-path. Remove Send confirmation. Make immediate. |
| Push +3 Days | ❌ Already Removed | Redundant with + button. |
| Push Send Confirmation | ❌ Remove | Adds friction without preventing meaningful mistakes. |
| Contextual Quick Actions | ❌ Remove | Visual clutter. Duplicates Call. PM doesn't need hints. |
| Feedback / Override | ✅ Keep (relocate) | Required by spec. Move to secondary menu. |
| Media Viewer | ✅ Keep | Reduces site visits. Core value. |
| Voice Playback | ✅ Keep | Specified inbound channel. |
| Filter Badges | ✅ Keep | Focus on Red/Yellow. Low complexity. |
| Auto-Refresh | ✅ Keep | Removes manual refresh work. |
| Escalation Banners | ❌ Already Removed | Card list is sufficient. |
| Delegate Status Buttons | ✅ Keep | Reduces phone calls. Conditional visibility. |

---

## Final Tally

| Decision | Count |
|---|---|
| ✅ Keep unchanged | 6 |
| ✅ Keep (with minor modifications) | 3 |
| ⚠️ Modify (behavior change) | 1 |
| ❌ Remove | 2 |
| ❌ Already removed | 2 |

## Recommended Action Items Before Sprint 1

1. **Push +1 Day**: Remove Send confirmation. Push is immediate. Keep cumulative label.
2. **Contextual Quick Actions**: Remove the entire section from cards.
3. **Feedback widget**: Move to secondary menu (⋯) — keep functionality, reduce prominence.
4. **Date modal**: Remove inline Notify checkboxes. Notifications handled automatically.
5. **Delegate**: Add default routing per project. Keep manual override.
