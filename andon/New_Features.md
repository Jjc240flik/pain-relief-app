# New Features & Future Improvements

This document captures high-value ideas that were discussed during development of the SMS Andon System but are not part of the current MVP scope. They are captured here for visibility, prioritisation, and planning — not as active commitments. Each entry includes a value assessment, effort estimate, and recommendation to help decide when to pick them up.

### How to Remove or Archive Features

To keep this document clean and relevant:

- If a feature is **no longer needed or has been built**, move it to a new section at the bottom called **"Archived / Removed Features"**. Add the date and a short reason why it was removed or archived.
- **Do not delete entries completely** unless they were added by mistake. Keeping history helps with future decision-making.
- If a feature is **partially built or deprioritized**, move it to **"On Hold"** or **"Deferred"** instead of deleting it.

This keeps the document useful as a living backlog rather than becoming cluttered with outdated ideas.

---

## 1. Immediate Contextual Actions on Issue View

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

## 2. Auto-Generated Escalation Group Text

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

## 3. Plug-in / Integration Layer (Zapier + Builder Platforms)

- **Value:** High
- **Effort:** Medium–High
- **Recommendation:** Do not build during active MVP. Add this after the core system (SMS loop, Dashboard, Classifier, and media handling) is stable and Jim is actively using the app daily. This should be treated as a post-MVP capability.

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

# Completed Features

Features that have been built and are currently live in the system. Each entry includes the delivery date and a summary of what was shipped.

---

## 1. "Last Verified" Activity Indicators

- **Completed:** July 18, 2026
- **Delivered:** Enhanced dashboard card labels showing specific response types — "✓ Onsite 7:46 AM", "⚠ Behind 7:45 AM", "🔴 Issue Reported 9:12 AM", "📝 Message Received 2:31 PM", "⚠ Unconfirmed 3:32 AM". Labels are trade-aware and update in real time as new replies come in. Option B+C logic ensures "Behind" is only shown when a proactive check-in was actually sent.

---

## 2. Delegate Button (Internal Task Assignment)

- **Completed:** July 18, 2026
- **Delivered:** "👥 Delegate" button on every Red/Yellow dashboard card. Opens a modal with team member checkboxes (Brian, Clint, Office Admin, Interior Designer) and a note field. Issue card updates with delegation badge showing assignee and status. Assigned person can mark as In Progress / Resolved. PM can Reclaim the task. All activity logged in Events table. Database: `delegated_to`, `delegated_by`, `delegation_note`, `delegation_status` columns on `schedule_items`.

---

## 3. Internal Metrics & Performance Dashboard

- **Completed:** July 18, 2026
- **Delivered:** Protected admin analytics page at `/admin/analytics` with four sections — Usage Metrics (SMS, MMS, Voice, Email counts + daily trend chart), Cost Estimates (Twilio/Whisper costs + projected monthly), Issue & Classifier Insights (Red/Yellow counts, correction rate, issues by trade, top subcontractors), System Health (schedules, media events). Configurable 7/30/90-day date range filter. All metrics derived from existing `events` table.

---

## 4. Usage Monitoring & Alerts

- **Completed:** July 18, 2026
- **Delivered:** Alert configuration page at `/admin/alerts` with toggle switches and threshold inputs for three alert types — Monthly Spend Limit, Daily Message Volume, Media Storage Growth. Active alerts display inline on the analytics page. Config stored in `alerts_config.json`. Alerts evaluate when analytics page loads.

---

## 5. Subcontractor Performance Scorecard

- **Completed:** July 18, 2026
- **Delivered:** Sortable scorecard table at `/admin/scorecard` with per-subcontractor metrics — Red/Yellow issue count, Behind flags, Classification Corrections, Delegation count and completion rate. Trade filter tabs. Visual highlights for repeat offenders (3+ Red or 3+ Behind). All metrics derived from existing `events`, `schedule_items`, and `contacts` data.

---

## 6. Onboarding Flow + Contact Import

- **Completed:** July 18, 2026
- **Delivered:** Three-step onboarding wizard at `/onboarding` — Welcome page with overview, CSV upload with downloadable template, manual single-contact form, and post-import success screen with counts. Users can skip and return later via `/admin/contacts`. CSV parser handles duplicate detection (updates existing by phone).

---

## 7. ClassifierEngine v3 + Graded Keyword Import

- **Completed:** July 18, 2026
- **Delivered:** ClassifierEngine v3 with trade severity matrix (1.3–0.85 multipliers), multi-hit scoring (3+ Yellow keywords upgrade to Red), expanded keyword lists (200+ across 9 categories), and graded keyword integration via `POST /admin/import-keywords`. Graded Excel file (420/420 terms across 10 trades) imported to `keywords_rules.json`. Step 3f checks graded keywords before built-in lists.

---

## 8. Improved Feedback / Correction Experience

- **Completed:** July 18, 2026
- **Delivered:** Inline correction picker on every dashboard card — click 👎 to reveal Red/Yellow/Green buttons with optional comment field. Corrections update the card in real time and log original status, new status, and comment to Events table. Backend `resolve` endpoint accepts `correct_status` (R/Y/G) and `comment` parameters.

---

## 9. MMS Photo (Up to 5) + Video Support

- **Completed:** July 18, 2026
- **Delivered:** MMS handler detects up to 5 media items (photos + video) per message. Media downloaded from Twilio and stored to S3 or local fallback. Dashboard shows 📷 N photos badge with count, ▶️ Video button. Gallery modal with Prev/Next navigation and video player modal with browser-native playback. Media metadata stored in Event `raw_payload`.

---

## 10. Email Inbound (SendGrid)

- **Completed:** July 18, 2026
- **Delivered:** SendGrid Inbound Parse webhook at `/webhooks/sendgrid/inbound`. Receives email → resolves sender by email against contacts → passes through ClassifierEngine → logs as immutable Event with `channel='email'`. Unknown senders logged without classification.

---

## 11. Voice + MMS Inbound

- **Completed:** July 18, 2026
- **Delivered:** Twilio voice webhook with `<Record>` TwiML for voicemail. Recording callback downloads audio and transcribes via OpenAI Whisper API. Transcription passed through ClassifierEngine. Falls back gracefully without API key. MMS detection added to existing SMS webhook. All events logged with `channel='voice_message'` or media metadata in SMS events.
