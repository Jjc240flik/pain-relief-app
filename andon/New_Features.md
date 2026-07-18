# New Features & Future Improvements

This document captures high-value ideas that were discussed during development of the SMS Andon System but are not part of the current MVP scope. They are captured here for visibility, prioritisation, and planning — not as active commitments. Each entry includes a value assessment, effort estimate, and recommendation to help decide when to pick them up.

---

## 1. "Last Verified" Activity Indicators

- **Value:** Very High
- **Effort:** Low–Medium
- **Recommendation:** Strong candidate to add relatively soon. Directly solves one of Jim's biggest time wasters (driving to houses just to verify attendance).

### Description

Add a small, subtle label next to the time indicator on each dashboard card showing the specific response type — e.g. **"Onsite 7:46 AM"** or **"Response Pending since 7:45 AM"**. This gives Jim at-a-glance confirmation that a sub actually arrived without requiring a site visit or phone call.

Prioritise showing this for subs who have a history of being late or unreliable. The system already tracks `last_touch_ts` per schedule item — the feature would enrich the dashboard display with the nature of the last touch (scheduled arrival, completion check-in, issue report) rather than just the elapsed time.

### Rationale

Jim explicitly said his biggest time waste is *"driving around to see if people got there"*. Even a simple "Verified Onsite" badge would eliminate a large fraction of those unnecessary trips.

---

## 2. Immediate Contextual Actions on Issue View

- **Value:** High
- **Effort:** Medium
- **Recommendation:** Good post-MVP feature. Very useful once the core system is stable.

### Description

When viewing an active issue on the dashboard, surface quick action options relevant to that specific problem rather than generic buttons. For example:

- **Contact sub** — One-tap call or text linked to the issue's trade contact (partially built with the Call dropdown, but could be richer)
- **Order material** — Pre-filled message template for material shortages (e.g. "Need more drywall sheets at 9101 Forest Ave — can you deliver by tomorrow?")
- **Trigger a group message** — Pre-composed update to Brian + Clint summarising the issue and current status
- **Schedule a re-inspection** — Quick calendar action tied to the house and trade

The goal is to reduce context switching and let Jim act immediately while looking at the issue, without needing to open a separate app or compose a message from scratch.

### Rationale

Jim operates in a high-pressure environment where *"when 5 things go wrong at once"* he needs to act fast. Reducing the number of steps between seeing a problem and acting on it directly improves his throughput.

---

## 3. Auto-Generated Escalation Group Text

- **Value:** Medium
- **Effort:** Low
- **Recommendation:** Nice quality-of-life improvement. Can be added after the Classifier work is complete.

### Description

When the **Escalate** button is clicked (especially during high-pressure moments when multiple things go wrong simultaneously), automatically generate a pre-formatted group text message that includes key details:

- House address
- Issue summary (from the last inbound event)
- Trade affected
- Recommended action (from Jim, or a default "Needs attention")
- Current schedule impact

The message is sent to Brian (owner) and Clint (foreman) via SMS. Jim can review and edit the message before sending (or auto-send for speed).

This turns a manual "copy-paste-remember-who-to-tell" workflow into a single tap.

### Rationale

During the interview, Jim described that when multiple issues fire at once, he coordinates with Brian and Clint to *"divide and conquer"*. A pre-built escalation message ensures the right people get the right information immediately, without Jim having to compose it under pressure.

---

## 4. Delegate Button (Internal Task Assignment)

- **Value:** High
- **Effort:** Medium
- **Recommendation:** Add after the core system (SMS loop + Dashboard + Classifier) is stable and Jim is actively using it daily.

### Description

Jim (or any paid internal user) can click a **"Delegate"** button on any Red or Yellow issue. This opens a simple interface showing other paid staff members in the company:

- Office Admin
- Boss / Brian (Owner)
- Crew Foremen (Clint, etc.)
- Interior Designer
- Other relevant internal roles

Jim can assign the issue to one or more colleagues and add a short note — for example:

> *"Please call this sub and confirm material arrival"*
> *"Can you swing by 4925 Big Sky Pass this afternoon?"*

The assigned person receives a notification (initially via email or in-app, later possibly SMS) with:

- The house address
- The issue summary
- Jim's note
- A link to view the issue in the dashboard

The original issue card should display:

- Who it was delegated to (name or role)
- The status of the delegation (Pending / In Progress / Resolved)
- A brief preview of Jim's note

This feature is only available to paid internal users — not to external subcontractors.

### Future Considerations

- Track delegation history in the `events` table for full audit trail
- Allow the assigned person to mark the task as **"In Progress"** or **"Resolved"** with a follow-up note
- Support recurring delegations or templates for common issue types (e.g. *"Follow up on material delivery"*)
- Add SMS notification for urgent delegations as a later upgrade

### Rationale

Jim currently handles nearly every issue personally. During the interview, he described needing to *"divide and conquer"* when multiple things go wrong at once. A Delegate button lets him distribute work across the team without leaving the dashboard — reducing his personal bottleneck and keeping issues moving even when he's stretched thin.
