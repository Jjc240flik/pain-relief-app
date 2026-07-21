# PRD: TLG Andon — Flow Intelligence for Mid-Sized Home Builders (MVP)

## 1. Product Goal

Build a simple, stable, multi-channel Andon system for residential builders managing roughly 10–50 active homes.

The system should help project managers, superintendents, and foremen answer one question quickly:

> What needs my attention now to keep production moving?

The product should capture updates from subcontractors and field personnel through the easiest available channel, convert that information into structured construction events, evaluate schedule impact, and surface only meaningful Yellow and Red exceptions.

The product is not intended to replace a builder's ERP, accounting platform, estimating tool, or full construction-management system.

It is an operational attention layer.

---

## 2. Core Product Principles

1. **Manage flow, not projects.**  
   The product exists to identify production blockers, emerging risks, and the next best action.

2. **Adapt to the field.**  
   Field personnel should communicate through SMS, email, voice, photo, or other familiar channels without being forced into a new app.

3. **Lowest-effort input wins.**  
   The easier information is to submit, the more reliable the system becomes.

4. **Every screen answers one question.**  
   The daily dashboard answers: "What needs my attention?"

5. **Management by exception.**  
   Green work is hidden by default. Yellow and Red work remains visible until resolved.

6. **Complexity belongs in the backend.**  
   Parsing, grading, schedule maturity, dependencies, confidence, and orchestration remain invisible to the field user.

7. **Every feature must reduce a decision, phone call, or unnecessary site visit.**

---

## 3. Primary Users

### Daily User
- Superintendent
- Project Manager
- Foreman
- Assistant PM

### Buyer
- Builder owner
- Operations manager
- Regional manager

### External Contributors
- Subcontractors
- Suppliers
- Inspectors
- Designers
- Internal office staff

External contributors do not require platform accounts for MVP.

---

## 4. Status Model

### Green — Flowing
- Confirmed on track
- No known production impact
- Hidden from the daily exception view by default

### Yellow — Needs Attention
- Risk within the next 1–2 days
- Confirmed delay that is not yet blocking production
- Incomplete information requiring manager review
- A target date is threatened
- No response before an upcoming commitment
- Minor cleanup or quality issue

### Red — Production Blocked
- Current production is stopped
- A crew is on site and cannot proceed
- A confirmed downstream trade or inspection is blocked
- A critical-path commitment is missed
- A safety, structural, code, or urgent compliance issue exists
- PM action is required today

The incoming message does not determine the final color by itself. Final severity is based on operational impact.

---

## 5. Construction Phases

The MVP supports these ten phases:

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

Each trade item may progress through:

- Not Scheduled
- Estimated
- Targeted
- Confirmed
- In Progress
- Complete
- Delayed
- Blocked
- Cancelled

---

## 6. Project Onboarding

Add a **+ Add Project** button beside **+ Add Contact**.

A project must be creatable in under five minutes.

### Required Project Fields
- Project name or lot number
- Street address
- City
- State
- ZIP code
- Assigned PM or superintendent
- Estimated Start or Target Start

### Optional Project Fields
- Community or development
- Internal project number
- Estimated Completion
- Target Completion
- Current project phase
- Current trade
- Next planned trade
- Notes

### Date Types
- **Estimated Start** — flexible planning date
- **Target Start** — current operational goal
- **Confirmed Start** — direct commitment from the assigned trade
- **Actual Start** — work physically began

Use date authority in this order:

1. Actual
2. Confirmed
3. Target
4. Estimated
5. None

### Trade Schedule
The trade schedule is optional and collapsed by default.

For each trade:
- Trade
- Assigned contact
- Estimated start
- Target start
- Confirmed start
- Estimated duration
- Target completion
- Preceding trade
- Dependent trades
- Inspection required
- Critical-path indicator
- Notes

Projects may be created with:
- No schedule
- Estimated dates only
- Target schedule
- Partial schedule
- Full schedule

Missing schedule data must never create a Yellow or Red card by itself.

---

## 7. Contact Onboarding

Contacts may be added independently or while onboarding a project.

### Contact Fields
- Name
- Company
- Trade / role
- Phone
- Email
- Manager name
- Manager phone
- Preferred contact method
- Escalation contact
- Notes

### Project Contact Assignment
Contacts may be assigned as:
- Superintendent
- PM
- Owner
- Office
- Trade contact
- Trade manager
- Supplier
- Inspector
- Designer
- Other

The contact directory is intended for onboarding and fast reference, not as a CRM.

---

## 8. Inbound Channels

All inbound channels feed the same processing pipeline.

### Supported in MVP
1. SMS
2. MMS photos
3. Email
4. Phone voicemail
5. Voice-note attachment
6. Manual PM entry

### Future
- Calendar integration
- Inspection feed
- ERP / project-management integrations
- GPS check-in
- AI phone calls
- Supplier feeds
- Public API / Zapier integration

---

## 9. Unified Processing Pipeline

Every inbound item follows this sequence:

1. Receive and store raw input
2. Validate source
3. Identify sender
4. Resolve project and trade context
5. Run keyword and phrase classifier
6. Use AI interpretation only when needed
7. Create a structured construction event
8. Evaluate project schedule maturity
9. Evaluate production-flow impact
10. Store Language Grade
11. Store Flow Grade
12. Create Final Card Status
13. Notify the PM if required
14. Preserve all decisions in the audit log

The system must never overwrite an earlier grading stage.

---

## 10. Grading Layers

### 10.1 Language Grade
Produced by the existing keyword and phrase classifier.

Stores:
- Matched keywords
- Matched phrases
- Likely trade
- Preliminary severity
- Keyword confidence

Language Grade is a language-risk signal only.

### 10.2 Structured Event
Produced by deterministic parsing or AI interpretation.

Examples:
- trade_confirmed
- trade_delayed
- trade_cancelled
- trade_no_show
- trade_on_site
- work_started
- work_completed
- work_incomplete
- work_blocked
- inspection_failed
- material_delayed
- safety_issue
- quality_issue
- permit_issue
- unknown_issue

### 10.3 Flow Grade
Produced by schedule and dependency rules.

Evaluates:
- Production blocked
- Critical path
- Active crew impact
- Next-trade impact
- Inspection impact
- Deadline impact
- Available float
- Schedule maturity

### 10.4 Final Card Status
The color shown to the PM.

Normally based on Flow Grade.

### 10.5 Manager Override
The PM may override the final status.

Store:
- Original status
- New status
- Reason
- User
- Timestamp

---

## 11. AI Responsibilities

AI may:
- Interpret free-form messages
- Extract dates, trades, reasons, and commitments
- Interpret voice transcriptions
- Interpret image captions
- Identify ambiguity
- Ask clarification questions
- Summarize message threads
- Return structured JSON

AI must not:
- Invent a schedule
- Invent dependencies
- Invent contacts
- Invent deadlines or cost impact
- Silently move confirmed dates
- Decide Red solely from emotional or negative language
- Replace deterministic flow rules

AI translates. Rules decide.

---

## 12. Keyword and Phrase Classifier

The existing graded keyword library remains the first classification layer.

Requirements:
- Phrase matches take precedence over individual-word matches
- Trade-specific phrases take precedence over broad words
- Full-sentence meaning must be considered
- Simple replies such as `1`, `2`, `3`, `YES`, `NO`, `DONE`, and `DELAYED` should bypass AI
- Conflicting or ambiguous language should trigger AI interpretation
- Preserve all matches for audit and tuning

---

## 13. Schedule Maturity

Classify each project as:

- `no_schedule`
- `estimated_only`
- `target_schedule`
- `partial_schedule`
- `full_schedule`

Rules:
- Estimated dates create planning context
- Target dates represent operational intent
- Confirmed dates represent a commitment
- Actual dates represent completed reality
- A missed estimated date cannot create Red by itself
- A missed target date normally creates Yellow
- A missed confirmed date may create Red if flow is blocked
- No schedule means the engine must grade conservatively

---

## 14. Outbound Communication

All proactive check-ins remain SMS-first for MVP.

### Quiet Hours
- Outbound automation: 7:00 AM–7:00 PM local time
- Inbound accepted 24/7
- Red emergency notifications may break quiet hours

### Rate Limit
Maximum one automated outbound check-in per trade per project per day, unless:
- The last response was Issue
- A clarification is required
- A manager manually triggers outreach

### Readiness Check
"TLG – Confirming [Trade] is still on for [Address] on [Date]. Reply 1=Yes, 2=No, 3=Issue."

### Day-Before Check
"TLG – Final check: Ready for [Trade] tomorrow at [Address]? Reply 1=Yes, 2=No, 3=Issue."

### Completion Check
"TLG – Did you finish [Trade] at [Address] today? Reply 1=Complete, 2=Partial, 3=Issue. Site left clean? A=Yes, B=No."

Cleanup `B=No` creates Yellow unless a stronger flow rule applies.

---

## 15. Daily Dashboard

Show Yellow and Red cards only by default.

Sort oldest unresolved cards first.

Each card displays:
- Status color
- Project city and address
- Trade
- Event summary
- Time since created
- Impact summary
- Recommended action
- Source channel icon
- Original media access if available

### Card Actions
- Resolve
- Date
- Call
- Delegate

No additional daily-dashboard controls are required for project onboarding, AI grading, confidence, or schedule maturity.

### Date Action
The Date action may allow:
- Move this trade only
- Move next trade
- Select multiple downstream trades
- Manual review
- Notify affected contacts

Confirmed dates must never be silently overwritten.

---

## 16. Immutable Audit Log

Every event must preserve:
- Raw message
- Source channel
- Original media
- Sender
- Project
- Trade
- Language Grade
- Structured Event
- Flow Grade
- Final Card Status
- Manager Override
- Actions taken
- Notifications sent
- Resolution
- Resolution time
- Classification feedback

Cards are temporary. Events are permanent.

---

## 17. Integration Strategy

The product should be designed as an additive operational layer.

Future integration targets:
- Buildertrend
- JobTread
- Procore
- Contractor Foreman
- Fieldwire
- BuildBook
- Zapier
- Google Calendar
- Microsoft 365
- Public REST API
- Webhooks

The system must support both:
- Builders who enter projects manually
- Builders who sync schedule and contact data from another system

Integrations should reduce duplicate entry and should not require replacing the builder's primary system.

---

## 18. Special Rules

### Foundation / Concrete
- Optional midpoint confirmation
- Structural, pour, engineering, and failed-inspection issues may escalate directly to the PM
- Cleanup failures are Yellow unless flow is blocked

### Framing
- Optional midpoint confirmation
- Structural, engineering, truss, or failed-inspection issues may escalate immediately
- Other issues follow normal Flow Grade rules

### Selections
If a message contains selection-related content:
- Forward full content and project address to the assigned designer
- Log question and response
- Fallback to PM if no designer is configured
- Continue normal flow grading when the message also affects production

---

## 19. Explicitly Out of Scope for MVP

- Full accounting
- Estimating
- Invoicing
- Change-order management
- Homeowner portal
- Full CRM
- Live call answering
- Complex IVR
- Weather automation
- Automated inspection integrations
- Automatic global schedule cascading
- Predictive subcontractor scoring
- Fully autonomous AI scheduling
- Full replacement of an existing construction-management system

---

## 20. MVP Success Criteria

The MVP succeeds when:
- A PM can onboard one project in under five minutes
- A subcontractor can send an update without an account
- The system correctly maps the message to project and trade
- Language Grade and Flow Grade are stored separately
- A Yellow or Red card appears when action is required
- The PM can understand the card in under five seconds
- The PM can act using Resolve, Date, Call, or Delegate
- The issue remains visible until resolved
- All actions remain auditable
- The system catches at least one meaningful issue earlier than the current phone-and-memory process
