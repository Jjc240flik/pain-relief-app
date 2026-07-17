# PRD: SMS Andon System for Mid-Sized Home Builders (MVP)

## Goal
Build a simple, stable multi-channel Andon system that tells the Project Manager (Jim) and his foreman/assistant (Clint) which houses are Red or Yellow without requiring phone calls, texts, or site visits to confirm status.

Red = progress blocked or next trade cannot start. PM must act today.  
Yellow = at risk within 1–2 days or minor issue needing monitoring.  
Green = confirmed on track (hidden from daily view by default).

## Core Principles
- Extremely low friction for subcontractors. They can communicate via whatever method is easiest for them (SMS, email, phone call, or voice message).
- System (not the sub) decides Red vs Yellow on every inbound message.
- Every piece of inbound information is logged immutably with full content + source channel.
- Quiet hours: outbound texts only 7:00 AM – 7:00 PM. Incoming messages accepted 24/7. Red emergency notifications can break quiet hours.
- Rate limit: maximum one automated outbound text per trade per house per day (unless previous reply was Issue).

## MVP Phases (10 individual phases)
1. Foundation / Concrete
2. Framing
3. Plumbing Rough
4. HVAC Rough
5. Electrical Rough
6. Drywall / Plaster
7. Paint
8. Flooring
9. Cabinets
10. Finish Work

Each phase has only three system states: Scheduled → In Progress → Complete.

## Data Model

### Houses
- id
- address
- current_phase
- overall_status (R / Y / G)
- notes

### Schedule
- house_id
- trade (enum of the 10 phases above)
- scheduled_start
- scheduled_end
- assigned_phone
- status (R / Y / G)
- last_touch_ts
- cleanup_confirmed (boolean)
- readiness_lead_days (integer – configurable per trade)

### Contacts
- trade
- name
- company
- phone
- email
- notes (e.g. "needs extra reminders")

### Events (immutable audit log)
- timestamp
- house_id
- trade
- direction (inbound / outbound)
- channel (sms / email / phone_call / voice_message)
- full_text (or transcription)
- original_media_url (for voice recordings)
- outcome (status change or null)
- triggered_by (project manager / foreman / sub)
- confidence_score (for transcribed or parsed messages)

## Outbound Communication (SMS only)
All proactive check-ins remain SMS only.

### 1. Configurable Readiness Check
Each trade has its own readiness window (60 days down to 24 hours before scheduled start).  
Defaults (editable by project manager at any time):
- Framing & Foundation/Concrete → 14 days
- Plumbing / HVAC / Electrical Rough → 7 days
- Drywall / Paint / Flooring → 5 days
- Cabinets / Finish Work → 5 days

Text:  
"TLG – Confirming [Trade] still on for [Address] on [Date]. Reply 1=Yes 2=No 3=Issue"

### 2. Day-Before Confirmation
"TLG – Final check: Ready for [Trade] tomorrow at [Address]? 1=Yes 2=No 3=Issue / site not ready"

### 3. Completion + Cleanup Check
"TLG – Did you finish [Trade] at [Address] today?  
1=Yes full complete  
2=Partial  
3=Issue blocking next  
Also: Site left clean? A=Yes B=No"

Any B=No → status = Yellow.

## Inbound Channels (All four feed the same pipeline)
1. SMS / Text – Structured replies (1/2/3) and free-form "ISSUE [description] at [Address]"
2. Email – Dedicated inbound address. System parses subject + body.
3. Phone Calls – Dedicated number routes to voicemail with short prompt.
4. Voice Messages – Voicemail or MMS voice notes. Full audio stored + transcribed.

Unified processing: Identify sender → extract house/trade → transcribe if voice → classify severity (keywords + confidence) → update status → notify → log everything with channel and confidence_score.

## Special Weighting

### Foundation / Concrete
- Extra midpoint confirmation during scheduled window
- Any Red escalates to Jim (project manager) only
- Cleanup failure = Yellow

### Framing
- Extra midpoint confirmation
- Selective escalation: only structural / engineering / inspection failure issues escalate to Jim (project manager). All other Framing issues stay with Jim + Clint (foreman).
- After MVP launch: short interview with framing crews to extract real severity keywords for better automatic classification.

## Hybrid Selections Handling
If any inbound message (any channel) contains keywords such as paint, color, finish, selection, what color, hardware, fixture, etc.:

→ Automatically forward the full message (or transcription) + house address to the interior designer.  
→ Log question and answer against the house.  
→ Fallback to Jim if no designer number is configured.

## Daily View (Jim & Clint)
Show only Red and Yellow houses.

Each row displays:
- Address
- Trade
- Last message / transcription (with channel icon)
- Time since last update
- Confidence indicator (if transcribed)

One-tap actions:
- Resolve (set to Green)
- Push +1 day
- Push +3 days
- Custom date change (simple date picker)
- Push this trade and notify next sub (sends both SMS and email to the subsequent trade with new date)
- Escalate to owner (manual)
- Listen to original voice recording (if available)

All schedule changes are logged in Events.

## Implementation Order
1. Data model + Contacts import + Events table with channel + triggered_by fields
2. Quiet hours + rate limiting + immutable logging
3. Outbound SMS flows (configurable readiness + day-before + completion)
4. Inbound SMS handling (structured + free-form ISSUE)
5. Email inbound parsing
6. Dedicated phone number + voicemail + transcription pipeline
7. Unified classification engine (keywords + confidence scoring)
8. Daily Red/Yellow view + quick schedule actions (including one-trade push + SMS/email notify)
9. Hybrid selections forwarding
10. Extra midpoint checks + selective escalation rules for Foundation/Concrete and Framing

## Explicitly Out of Scope for MVP
- Live call answering or complex IVR menus
- Full micro-step tracking from the master checklist
- Automatic global date cascading across all remaining trades (Instead, include a manual "Push this trade and notify next sub" action that sends both SMS and email to the subsequent trade)
- Weather or inspection automation
- Invoice tracking
- Perfect NLP (start simple with keyword rules + confidence scoring and improve iteratively)

## Notes for Build
- Transcription service must be reliable (start with a proven provider such as Deepgram, AssemblyAI, or OpenAI Whisper).
- Always store original audio even after transcription.
- All channels must support the same "ISSUE + description" mental model so classification stays consistent.
- Start with known contacts only. Unknown senders go to a review queue.
- The current PRD defines the "what" (user flows, data model, business logic, and required behaviors). Technical backend setup details (exact database schema with field types/indexes, Twilio/SendGrid configuration, transcription provider integration code, NLP keyword lists and thresholds, authentication, deployment architecture, error handling, monitoring, etc.) belong in a separate Technical Specification / Architecture document that we will create once this PRD is approved.

Build this multi-channel version. The inbound flexibility will significantly increase real issue capture while keeping outbound communication simple and predictable for the subs.
