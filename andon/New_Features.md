# New Features & Future Improvements

This document captures high-value ideas that were discussed during development of the SMS Andon System but are not part of the current MVP scope. They are captured here for visibility, prioritisation, and planning — not as active commitments. Each entry includes a value assessment, effort estimate, and recommendation to help decide when to pick them up.

### How to Remove or Archive Features

To keep this document clean and relevant:

- If a feature is **no longer needed or has been built**, move it to a new section at the bottom called **"Completed Features"**. Add the date and a short reason why it was removed or archived.
- **Do not delete entries completely** unless they were added by mistake. Keeping history helps with future decision-making.
- If a feature is **partially built or deprioritized**, move it to **"On Hold"** or **"Deferred"** instead of deleting it.

This keeps the document useful as a living backlog rather than becoming cluttered with outdated ideas.

---

## 1. Plug-in / Integration Layer (Zapier + Builder Platforms)

- **Value:** High
- **Effort:** Medium–High
- **Recommendation:** Do not build during active MVP. Add this after the core system is stable and Jim is actively using the app daily. This should be treated as a post-MVP capability.

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
- **Delivered:** "👥 Delegate" button on every Red/Yellow dashboard card. Opens a modal with team member checkboxes (Brian, Clint, Office Admin, Interior Designer) and a note field. Issue card updates with delegation badge showing assignee and status. Assigned person can mark as In Progress / Resolved. PM can Reclaim the task. All activity logged in Events table.

---

## 3. Internal Metrics & Performance Dashboard

- **Completed:** July 18, 2026
- **Delivered:** Protected admin analytics page at `/admin/analytics` with Usage Metrics (SMS, MMS, Voice, Email + daily trend chart), Cost Estimates (Twilio/Whisper costs + projected monthly), Issue & Classifier Insights (Red/Yellow counts, correction rate, issues by trade, top subs), System Health. Configurable 7/30/90-day date range.

---

## 4. Usage Monitoring & Alerts

- **Completed:** July 18, 2026
- **Delivered:** Alert configuration at `/admin/alerts` with toggle switches and thresholds for Monthly Spend Limit, Daily Message Volume, Media Storage Growth. Active alerts display inline on the analytics page. Config stored in `alerts_config.json`.

---

## 5. Subcontractor Performance Scorecard

- **Completed:** July 18, 2026
- **Delivered:** Sortable scorecard at `/admin/scorecard` with per-sub metrics — Red/Yellow count, Behind flags, Corrections, Delegation count/completion rate. Trade filter tabs. Visual highlights for repeat offenders.

---

## 6. Onboarding Flow + Contact Import

- **Completed:** July 18, 2026
- **Delivered:** Three-step onboarding wizard at `/onboarding` — Welcome page, CSV upload with downloadable template, manual contact form, success screen with counts. CSV parser handles duplicates. Users can skip and return via `/admin/contacts`.

---

## 7. ClassifierEngine v3 + Graded Keyword Import

- **Completed:** July 18, 2026
- **Delivered:** ClassifierEngine v3 with trade severity matrix (1.3–0.85), multi-hit scoring (3+ Yellow → Red upgrade), expanded keyword lists (200+ across 9 categories), and graded keyword integration via `POST /admin/import-keywords`. 420 graded terms across 10 trades.

---

## 8. Improved Feedback / Correction Experience

- **Completed:** July 18, 2026
- **Delivered:** Inline correction picker on every dashboard card — click 👎 to reveal Red/Yellow/Green buttons with optional comment. Corrections log original status, new status, and comment to Events table.

---

## 9. MMS Photo (Up to 5) + Video Support

- **Completed:** July 18, 2026
- **Delivered:** MMS handler detects up to 5 media items per message. Dashboard shows 📷 N photos badge, ▶️ Video button. Gallery modal with Prev/Next navigation and video player. Media stored to S3 or local fallback.

---

## 10. Email Inbound (SendGrid)

- **Completed:** July 18, 2026
- **Delivered:** SendGrid Inbound Parse webhook at `/webhooks/sendgrid/inbound`. Email → sender resolution → ClassifierEngine → logged as Event with `channel='email'`.

---

## 11. Voice + MMS Inbound

- **Completed:** July 18, 2026
- **Delivered:** Twilio voice webhook with voicemail recording. Recording callback transcribes via OpenAI Whisper → ClassifierEngine. Falls back gracefully without API key. MMS detection on existing SMS webhook.

---

## 12. Contextual Quick Actions

- **Completed:** July 19, 2026
- **Delivered:** Trade-specific action buttons on dashboard cards — "📐 Check Truss Specs", "📞 Call Supplier", "🔍 Request Inspection", "🧹 Flag for Cleanup", "📢 Notify Next Trade", and more. Actions defined per trade in `CONTEXTUAL_ACTIONS` dictionary. Pre-fill delegation note or call sub directly.

---

## 13. Auto-Generated Escalation Messages

- **Completed:** July 19, 2026
- **Delivered:** Escalation banners appear on dashboard when conditions are met (Red issue open > 4h, multiple Red on same house, high-severity keywords). Two escalation groups: "Critical Issues Group" (Brian + Clint) and "Owner Only" (Brian). PM can review and click "Send Escalation" to log and dismiss. Config stored in `escalation_config.json`.
