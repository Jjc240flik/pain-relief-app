# New Features & Future Improvements

This document captures high-value ideas that were discussed during development of the SMS Andon System but are not part of the current MVP scope. They are captured here for visibility, prioritisation, and planning — not as active commitments. Each entry includes a value assessment, effort estimate, and recommendation to help decide when to pick them up.

### How to Remove or Archive Features

To keep this document clean and relevant:

- If a feature is **no longer needed or has been built**, move it to a new section at the bottom called **"Archived / Removed Features"**. Add the date and a short reason why it was removed or archived.
- **Do not delete entries completely** unless they were added by mistake. Keeping history helps with future decision-making.
- If a feature is **partially built or deprioritized**, move it to **"On Hold"** or **"Deferred"** instead of deleting it.

This keeps the document useful as a living backlog rather than becoming cluttered with outdated ideas.

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
- **Recommendation:** Add after the core system (SMS loop, Dashboard, Classifier, and media handling) is stable and Jim is actively using the app daily.

### Description

Jim can click a **"Delegate"** button on any Red or Yellow issue card.

This opens a simple interface showing other paid internal team members (Office Admin, Brian/Owner, Foremen, Interior Designer, etc.).

Jim can assign the issue to one or more colleagues and add a short note with instructions.

The assigned person receives a notification (email or in-app) with the house address, issue details, and Jim's note.

The original issue card on Jim's dashboard updates to show:
- Who the issue was delegated to
- Jim's note
- Current delegation status

The assigned person can update the status of the task (e.g. mark as **"In Progress"** or **"Resolved"**) and add comments. These updates should be visible back on the main dashboard.

Jim should **still see the issue** on his dashboard — it does not disappear after delegating.

Jim should be able to **reclaim or re-assign** the task if needed.

All delegation activity and updates are logged in the Events table for audit/history purposes.

This feature is only available to paid internal users, not to external subcontractors.

### Goal

Allow Jim to efficiently distribute work across his team instead of personally handling every issue, while maintaining full visibility and accountability.

### Future Considerations

- Support templates for common delegation notes.
- Allow recurring delegations or scheduled follow-ups.
- Add permission levels (e.g. who can delegate vs who can only receive tasks).

---

## 5. Internal Metrics & Performance Dashboard (Backend Data Center)

- **Value:** High
- **Effort:** Medium
- **Recommendation:** Add after the core system (SMS loop, Dashboard, Classifier, and Call button) is stable and Jim is actively using the app daily. This should not be built during active MVP development.

### Description

Create a protected internal dashboard (accessible only to paid staff / admin users) that shows how the Andon system is performing. The goal is to give Jim visibility into whether the system is actually helping him and where it can be improved — not just what's happening *in the field*, but how well the app itself is working.

Key metrics to track would include:

- **Message performance** — Total SMS sent vs received, response rates per trade, and how often subs engage with the automated check-in messages
- **Issue volume** — Number of Red and Yellow issues created over time (daily / weekly breakdown)
- **Resolution speed** — Average time from when an issue is flagged (Red or Yellow) until it is resolved (set back to Green)
- **Classifier performance** — How often Jim corrects classifications via the feedback endpoint; which keywords or trades produce the most corrections (this directly drives ClassifierEngine improvements)
- **"Behind" flag accuracy** — How many "Behind" alerts turned out to be real problems vs noise; correlation with Option C history tracking
- **Top problem areas** — Which trades, subcontractors, or houses are triggering the most issues; surfacing recurring patterns
- **System health** — Failed SMS deliveries, webhook errors, API response times, or other technical issues

### Future Considerations

- Start simple with a clean internal web page at a dedicated path (e.g. `/admin` or `/metrics`) rather than a full observability platform
- Over time, add visual charts, date range filters, and CSV export for offline analysis
- Eventually support multiple internal users with different permission levels
- Becomes especially valuable once multiple builders are using the system — helps identify patterns across companies, trades, and regions

### Rationale

Right now, there is no way to measure whether the Andon system is actually reducing Jim's workload. The core dashboard tells him what's wrong *right now*, but it doesn't tell him whether issues are resolving faster than before, which subs are most reliable, or whether the classifier is getting better over time. An internal metrics dashboard turns raw event data into actionable insight — making the system self-improving rather than just reactive.

---

## 6. Plug-in / Integration Layer (Zapier + Builder Platforms)

- **Value:** High
- **Effort:** Medium–High
- **Recommendation:** Do not build during active MVP. Add this after the core system (SMS loop, Dashboard, Classifier, and Call button) is stable and Jim is actively using the app daily. This should be treated as a post-MVP capability.

### Description

Make the app "plug-in ready" so it can easily connect with larger existing platforms that home builders already use — QuickBooks, Buildertrend, JobNimbus, ServiceTitan, and similar tools. The goal is to allow the Andon system to push and receive data from other systems instead of forcing builders to manage everything inside a single app.

Initial focus should be on **outbound integrations** — the app can send real-time events (new Red/Yellow issues, status changes, resolutions, etc.) to external systems when they happen. Over time, support **inbound actions** (e.g. creating an issue from another platform or updating a schedule status via API).

Ideally, offer a native **Zapier integration** so non-technical users can easily connect the app to hundreds of other tools without any custom development.

### Future Considerations

- Start with a clean **outbound webhook system** — the app fires structured JSON events to configurable external URLs when key actions occur (new issue, status change, resolution, escalation)
- Add **API key authentication** so external platforms can securely interact with the app
- Build a proper **public REST API** (even if simple at first, with documented endpoints)
- Eventually create a **Zapier app** so users can set up automations like:
  - *"When a new Red issue is created → Create a task in Buildertrend"*
  - *"When an issue is resolved → Update QuickBooks job status"*
  - *"When a sub is flagged Behind → Send a Slack alert"*
- Support both **push** (app sends data out) and **pull** (external apps query the app's data) capabilities
- Becomes especially valuable once multiple builders are using the system, as different companies will want to connect it to different tools

### Rationale

No home builder runs their entire operation inside a single app. They use QuickBooks for accounting, Buildertrend for project management, Slack for team chat, and dozens of other tools. If the Andon system is a closed silo, it becomes a *separate place* Jim has to check — which adds friction rather than removing it. A Zapier integration layer lets the app fit into whatever workflow Jim's team already has, turning it from a standalone tool into a piece of their broader operational stack.

---

## 7. Usage Monitoring & Alerts (Cost & Performance Tracking)

- **Value:** Medium–High
- **Effort:** Medium
- **Recommendation:** Add after the core system (SMS loop, Dashboard, Classifier, and media handling) is stable and Jim is actively using the app daily. This becomes more important once multiple builders or higher message volume is involved.

### Description

Create a protected internal section (or page) that allows Jim (and other admin users) to monitor how the system is being used. The goal is to provide visibility into usage patterns and help control costs at scale — especially around Twilio (SMS/MMS/Voice), OpenAI Whisper (transcription), and media storage.

Key metrics to track should include:

- **Message volume** — Total SMS, Email, and Voice messages sent and received over time (daily / weekly / monthly)
- **Media usage** — Number of photos and videos stored, total storage consumed
- **Issue velocity** — Number of Red and Yellow issues created per day or week
- **Classifier accuracy** — How often Jim corrects classifications (correction rate over time)
- **Resolution speed** — Average time from issue flagged to issue resolved

Add the ability to set simple **usage alerts** — for example, notify Jim when monthly SMS volume exceeds a certain threshold, or when storage consumption grows unusually fast.

All data should be retained until the project is marked as complete.

### Future Considerations

- Add charts and graphs for better visualisation of trends over time
- Allow filtering by trade, subcontractor, or house
- Support export of usage reports (CSV or PDF)
- Eventually allow multiple internal users with different permission levels to view usage data
- Add more advanced cost forecasting (e.g. projected monthly spend based on current usage patterns)

### Rationale

Right now, there is no way to see whether the system is being used efficiently or whether costs are growing as expected. Twilio charges per SMS segment, per MMS, and per minute of voice — and OpenAI charges per minute of audio transcribed. Without visibility into these numbers, cost overruns only get noticed when the bill arrives. A usage monitoring page gives Jim the data he needs to manage costs proactively rather than reactively.
