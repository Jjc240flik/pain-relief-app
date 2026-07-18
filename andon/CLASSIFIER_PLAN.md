# Classifier Improvement Plan

## Current State
The `ClassifierEngine` uses flat, trade-agnostic keyword lists for Red, Yellow, and Selection detection. It has no awareness of which construction trade a message relates to, no site-condition language, and no mechanism for handling low-confidence or ambiguous messages.

## Short-Term Improvements (Now — Implemented Below)

### 1. Trade-Aware Classification
- Pass the `trade` context from the inbound message pipeline into `classifier.classify(text, trade=None)`
- Create trade-specific keyword overrides for **Framing** and **Foundation/Concrete** (the two highest-risk trades per Jimmy's interview)
- Structural keywords (load-bearing, truss, collapse, inspection failure) get **Red** for Framing/Foundation but only **Yellow** for other trades
- Trade awareness uses a simple `{trade: {severity: [keywords]}}` dict — no ML needed

### 2. Site Cleanliness Detection (from Jimmy's Interview)
Jimmy's exact words: *"nobody wants to do... gets pushed off to the next trade"* and *"walk up to a job site and it looks like a tornado went through"*
- New **SITE_CLEANLINESS_KEYWORDS** list: debris, garbage, waste, swept, shop vac, roadway clean, materials stacked, dumpster, tornado, site cleanup, trash, job site messy, etc.
- Cleanliness issues default to **Yellow** — annoying but not blocking
- If message also contains "blocking", "can't start", "delay" → escalate to **Red**

### 3. Water/Moisture Detection (from Jimmy's Interview)
Jimmy said: *"Water and home building do not mix"* and *"Everything that comes with water... If I could never have to deal with water damage again"*
- New **WATER_KEYWORDS** list: water in basement, sump pump, dehumidifier, fans running, grading issue, standing water, heavy rain, flood, leak (expanded), moisture, condensation, wet, damp, etc.
- For **Foundation/Concrete**: any water keyword → **Red** (highest risk for this trade)
- For other trades: water keywords → **Yellow** (escalate to Red if structural language present)

### 4. Structural Severity Weighting
- **Framing** and **Foundation/Concrete** keywords like: truss, load bearing, structural, collapsed, inspection failure, cannot start
- → These ALWAYS produce **Red** for those trades
- → Same keywords for other trades produce **Yellow** (still concerning but less critical)

### 5. Low-Confidence / Ambiguous Handling
- If no keywords match AND confidence stays below 0.3 → return `needs_review=True`
- Dashboard can surface these for Jim to review
- Messages that partially match (e.g. one weak keyword match at confidence 0.4–0.5) also flagged

### 6. Classification Feedback Endpoint
- New dashboard action: `POST /dashboard/classify/{event_id}/correct?status=R|Y|G`
- Logs the correction as an Event
- Stores the corrected label for future classifier tuning

### 7. Expanded Selections Detection
- Add: what shade, what colour, cabinet style, counter material, backsplash, appliance color, light fixture, faucet style, door handle, tile color

## Medium-Term Improvements (After 100–200 Events)

- Build a **correction log table** to store `{original_classification, corrected_label, text, trade}` pairs
- Run weekly analysis on correction patterns to identify new keywords
- Introduce **per-trade threshold tuning** (e.g. framing triggers Red at fewer keyword hits than paint)
- Add **multi-keyword scoring**: if 3+ Yellow keywords appear in one message, upgrade to Red
- Incorporate **sender history**: if a sub has sent 3+ Yellow messages this week, auto-boost to Red

## Long-Term Direction (After 500+ Events)

- Lightweight ML: train a logistic regression classifier on the correction log data (features = TF-IDF unigrams + trade one-hot)
- Replace keyword rules with a hybrid system: ML suggestion with keyword rules as fallback override
- Add **sentiment analysis** for voicemail transcriptions
- Per-sub calibration: adjust thresholds based on each sub's historical message pattern
- Automated suggestion generation: "These 3 keywords were corrected 80% of the time — add to Red list?"
