# New Feature: Inbound Message Phrase Library (Voice + SMS + MMS)

## Goal
Capture every inbound message — **voice transcriptions, SMS texts, and MMS-extracted text** — and feed them into a persistent word/phrase library to improve classifier accuracy over time. This covers **all intake channels**, not just voice.

## Why
The classifier (v3) scores inbound messages against a keyword/phrase matrix. Currently every message is classified and then discarded. By building a persistent phrase library from **real subs' actual language** across all channels, we can:

- Discover new phrases subs actually say (vs. what we guessed during onboarding)
- Improve confidence scoring for all channels (not just voice)
- Build a feedback loop: corrections (👍👎) on any classified card update the phrase weights
- Generate a live phrase frequency report to manually merge into the master keyword list

## Channels Included

| Channel | Source | Phrases extracted from |
|---|---|---|
| **SMS** | `/webhooks/plivo/sms` | Raw `Text` field |
| **MMS** | `/webhooks/plivo/sms` | Caption text sent with photo/video |
| **Voice** | `/webhooks/plivo/recording` | Whisper transcription of audio |

## Proposed Architecture

### 1. Source Pipeline (all three channels feed the same phrase table)

The existing `InboundProcessor.process()` is the common entry point for every channel. After it runs classification and creates the event/card, we add a **phrase extraction step** that reads the final `full_text` and the classifier's `result` (trade, outcome, confidence).

```
Plivo SMS/MMS or Voice recording
       ↓
InboundProcessor.process()  (existing)
  - channel: "sms" | "voice_message"
  - raw_text: SMS body or voice transcript
       ↓
ClassifierEngine.classify()  (existing)
       ↓
Event + card created  (existing)
       ↓
[NEW] Extract phrases from raw_text
       ↓
[NEW] Upsert into inbound_phrases table
         - phrase, channel, trade, outcome, confidence
         - increment frequency if similar phrase exists
```

### 2. New Database Table (single table for all channels)

```sql
-- Phrases extracted from ALL inbound messages (SMS, MMS, Voice)
CREATE TABLE inbound_phrases (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id        UUID REFERENCES events(id),    -- source event
  channel         VARCHAR(20) NOT NULL,           -- 'sms', 'voice_message'
  phrase          TEXT NOT NULL,                  -- extracted n-gram / sentence
  trade           VARCHAR(30),                   -- trade from classifier
  outcome         CHAR(1),                       -- R/Y/G from classifier
  confidence      REAL,                          -- classifier confidence (0-1)
  frequency       INTEGER DEFAULT 1,             -- how many times seen
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_inbound_phrases_phrase ON inbound_phrases (phrase);
CREATE INDEX idx_inbound_phrases_trade ON inbound_phrases (trade);
CREATE INDEX idx_inbound_phrases_freq  ON inbound_phrases (frequency DESC);
```

A single `inbound_phrases` table covers all channels — no separate table per channel needed.

### 3. Processing Flow

**Step A: After classification (in InboundProcessor or a new PhraseExtractor service)**
- Take the raw text that was classified (SMS body or voice transcript)
- Normalize: lowercase, strip punctuation, collapse whitespace
- Split into sentences / meaningful segments
- Filter: skip common fillers, greetings, sign-offs
- For each remaining segment, check `inbound_phrases` for a similar existing entry:
  - If found → increment `frequency`, update `outcome`/`confidence` if they differ
  - If not found → insert new row with `channel`, `trade`, `outcome`, `confidence`

**Step B: Corrections update the phrase library**
- When a user clicks 👍 or 👎 on a card:
  - 👍 → confirms the current `trade`/`outcome` → increment `frequency` for matching phrases
  - 👎 with correction → update `trade`/`outcome` for the associated phrases

**Step C: Weekly / on-demand phrase library export**
- Query `inbound_phrases` where `frequency > N` (e.g. > 3) and `is_active = true`
- Format as CSV matching the existing `keywords_and_phrases_checklist.xlsx` schema
- Output via admin page: `/admin/phrase-library` with download option
- Admin reviews, approves, and merges into the master classifier keyword list

### 4. Admin UI

New page at `/admin/phrase-library` showing:
- Phrase table: phrase, channel source, trade, outcome, frequency, last seen
- Filter by channel (SMS / Voice / All), trade, min frequency
- Bulk-select phrases to mark "approved" (adds to classifier ruleset)
- "Export to CSV" button
- "Auto-merge high-frequency" button (merges phrases with frequency > threshold into active classifier)

### 5. Dependencies

- `OPENAI_API_KEY` (for voice transcription — already needed if voice is used)
- No additional packages — the phrase extraction is pure Python (regex + split logic)
- Existing `InboundProcessor` is the hook point

### 6. Implementation Order

1. Create `inbound_phrases` table
2. Add phrase extraction step inside `InboundProcessor.process()` after classification
3. Wire corrections (👍👎) to update phrase `frequency` / `outcome`
4. Build `/admin/phrase-library` admin page with filters + export
5. Add auto-merge of high-frequency phrases into active classifier ruleset

### Notes
- Voice transcription (Whisper) costs ~$0.006/minute — only applies to voice channel
- SMS text has zero additional cost — phrases are extracted from already-received messages
- The phrase library grows organically — the more messages processed, the better the classifier gets
- Plivo recordings expire after 24 hours — audio must be downloaded + transcribed promptly
