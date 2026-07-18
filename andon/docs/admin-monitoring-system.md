# Admin Monitoring System

## Overview

The Admin Monitoring System provides the app owner/administrator with deep visibility into usage, costs, and system performance. It is designed for backend decision-making — tracking how the system is being used, what it costs to run, and where improvements can be made.

**Access:** `GET /admin/analytics` — protected page intended for the app owner/admin only.

---

## Sections

### 1. Usage Metrics

Shows total event counts across all channels over a configurable time period (7, 30, or 90 days).

| Metric | Source | Calculation |
|---|---|---|
| Total Events | `events` table | Count of all events in the period |
| SMS | `events.channel = 'sms'` | Total SMS sent + received |
| MMS (Photos) | `events` with `raw_payload` containing media | Events with media attachments |
| Voice | `events.channel = 'voice_message'` | Voice recording events |
| Email | `events.channel = 'email'` | Email events |
| Voice Minutes | `events.channel = 'voice_message'` | Each recording ≈ 1 minute |

A daily trend bar chart shows SMS and Voice volume over the time period for quick visual pattern recognition.

### 2. Cost Estimates

Estimates running costs based on usage volume and configurable pricing rates.

| Cost Item | Rate | Source |
|---|---|---|
| SMS | $0.0079 / segment | Twilio SMS pricing |
| MMS | $0.02 / message | Twilio MMS pricing |
| Voice | $0.013 / minute | Twilio Voice pricing |
| Whisper | $0.006 / minute | OpenAI Whisper API pricing |
| Storage | $0.023 / GB / month | S3 or equivalent |

**Key displays:**
- **Total cost** for the selected time period
- **Projected monthly cost** — extrapolated from current trends
- Expandable pricing reference section showing all rates used

### 3. Issue & Classifier Insights

Tracks the classification system's performance and identifies patterns.

| Metric | Source | Purpose |
|---|---|---|
| Red Issues | `events.outcome = 'R'` | Count of critical issues |
| Yellow Issues | `events.outcome = 'Y'` | Count of warning-level issues |
| Corrections | `events.full_text LIKE '[CLASSIFICATION CORRECTION]%'` | How often the admin corrects classifications |
| Correction Rate | `corrections / (red + yellow) * 100` | Percentage of classifications that were wrong |
| Issues by Trade | `events.trade` grouped by count | Which trades generate the most issues |
| Top Subcontractors | `events.sender_phone` grouped by count | Which subs trigger the most Red/Yellow flags |

### 4. System Health

Monitors the operational health of the system.

| Metric | Source | Purpose |
|---|---|---|
| Total Schedules | `schedule_items` table | How many jobs are being tracked |
| Media Events | Events with `raw_payload` | Media storage growth tracking |
| Errors | Placeholder | Failed messages or webhook errors |
| Avg Resolution Time | Placeholder | Average time from flag to resolution |

---

## Data Sources

All metrics are derived from existing data in the system — no new database tables were created. The primary sources are:

- **`events` table** — All usage, classification, and cost data
- **`schedule_items` table** — Schedule and resolution tracking

---

## How to Access

1. Open the dashboard: `http://[your-server]:8000/admin/analytics`
2. Select a time period: **7d**, **30d**, or **90d** buttons at the top
3. Scroll through the four sections: Usage → Costs → Issues → Health

---

## Current Limitations

- **Error tracking**: `health.error_count` is a placeholder — needs webhook error logging to populate
- **Avg resolution time**: Not yet calculated from data — requires resolution-time tracking logic
- **Pricing rates**: Hard-coded in `DEFAULT_RATES` — can be made configurable via API or UI
- **No CSV export**: Planned for future enhancement
- **No charts**: Uses simple CSS bar charts — no JavaScript charting library (MVP design choice)
- **Single admin user**: No multi-user permissions yet

---

## Future Enhancements

- Add CSV/PDF export for usage and cost reports
- Integrate charting library (Chart.js or similar) for richer visualisations
- Add email/SMS alert when monthly spend exceeds configurable threshold
- Track and display error rates from failed webhooks
- Add filtering by trade, subcontractor, or house
- Support multiple admin users with different permission levels
- Add cost forecasting (e.g. "projected spend this month based on usage")
- Integrate with actual billing APIs (Twilio, OpenAI) for real cost data
