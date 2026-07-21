# Classifier v3 → v4 Gap Analysis

**Date:** July 2026

## What v3 Has

- Trade-aware keyword scoring (multi-hit)
- Severity matrix per trade
- Medium-risk trade category (plumbing, electrical, HVAC)
- Correction tracking
- Feedback loop (👍👎)
- Graded keyword rules from JSON
- Structured single-char reply handling (1/2/3/A/B)
- Water, structural, cleanliness checks

## What v4 Adds

### 1. Schedule Maturity Model (NEW)
v3 has no concept of schedule maturity. v4 requires knowing whether a project has:
- No schedule
- Estimated dates only
- Target dates
- Partial schedule
- Full schedule

**Impact:** v3 currently treats all dates the same. v4 needs to distinguish estimated vs target vs confirmed vs actual dates, and grade severity differently based on which type of date is affected.

### 2. Date Hierarchy (NEW)
v3 has no date-type awareness. v4 defines:
1. Actual date (strongest)
2. Confirmed date (commitment from trade)
3. Target date (operational intention)
4. Estimated date (planning context)
5. No date

**Impact:** A delay against an estimated date should rarely be Red. A delay against a confirmed date on the critical path may be Red. v3 can't make this distinction.

### 3. Project Contact Logic (NEW)
v3 doesn't resolve contacts per project. v4 requires:
- Assigned sub contact → sub manager → superintendent → PM → office → owner
- Contact recommendations tied to the affected trade
- Role-aware notification suggestions

**Impact:** Requires `project_contacts` data to be available at classification time. Currently contacts are looked up by trade only.

### 4. Standardized Event Types (NEW)
v3 uses keyword categories (Red/Yellow/Green). v4 requires a structured event type:
- `trade_delayed, trade_cancelled, inspection_failed, material_delayed, etc.`

**Impact:** v3 output is (status, confidence). v4 output includes an event_type enum that feeds downstream logic.

### 5. Impact Assessment (NEW)
v3 grades the message text. v4 grades the **operational impact**:
- Is another trade blocked?
- Is an inspection at risk?
- Is a crew scheduled within 72h?
- Is the closing date at risk?
- Is there enough float?

**Impact:** v3 evaluates what the message says. v4 evaluates what the message means for the build. This requires schedule + dependency data.

### 6. Time-Based Escalation (NEW)
v4 defines escalation windows:
- Target date within 72h → Yellow
- Confirmed start within 24h → Yellow
- Confirmed start missed → Red if critical, else Yellow
- Yellow unresolved beyond float → Red

**Impact:** v3 has no time-based escalation. Cards stay at their initial grade unless manually corrected.

### 7. Foreman Card Format (NEW)
v4 output includes a `foreman_card` section with:
- Title (5-second summary)
- Issue summary
- Impact summary
- Recommended action text

**Impact:** v3 returns structured data. v4 adds a human-readable card format optimized for the superintendent.

### 8. Date Change Recommendations (NEW)
v4 recommends date change scope:
- no_date_change
- change_this_trade_only
- change_this_trade_and_next_trade
- cascade_selected_trades
- manual_review_required

**Impact:** v3 doesn't recommend date changes. v4 connects classification to the scheduling interface.

### 9. Confidence Scoring (DIFFERENT)
v3 uses keyword hit counts for confidence. v4 adds:
- Schedule completeness affects confidence
- Date type availability affects confidence
- Event certainty (confirmed/likely/possible/unclear) is explicit

### 10. Missing Information Tracking (NEW)
v4 explicitly tracks what's missing:
- Missing target dates
- Missing downstream trades
- Missing inspection dates
- Missing contact info

**Impact:** v3 either guesses or returns low confidence. v4 surfaces exactly what data is needed to improve the grade.

## Implementation Order

1. **Date type awareness** — Add estimated/target/confirmed/actual date fields to the schedule model. Update the `InboundProcessor` to pass date type info to the classifier.

2. **Schedule maturity classifier** — Classify the project schedule as one of the five maturity levels. This gates all downstream severity logic.

3. **Event type extraction** — Add event type inference to the classifier output. Map from keywords to standardized event types.

4. **Impact assessment** — Add downstream impact evaluation using the schedule + dependency data. Requires trade sequence model.

5. **Time-based escalation** — Add escalation rules based on how long a card has been at Yellow vs the project's available float.

6. **Foreman card format** — Update the card template to use the structured foreman_card output.

7. **Project contact resolution** — Add per-project contact lookup with role-aware recommendation logic.

8. **Date change recommendations** — Connect classifier output to the date cascade UI (already partially built).
