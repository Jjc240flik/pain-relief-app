# Future Feature: Public REST API (Decision Engine)

**Source:** Vision Board — The Operations Layer architecture

## Goal
Expose Andon's core functionality as a public REST API so external platforms (Buildertrend, Procore, JobTread, etc.) can push events into the system and read status back out.

## Why
Andon's moat is the Decision Engine — the classifier, escalation logic, and uncertainty-reduction layer. A public API lets every other platform feed into it without Andon needing to build native integrations for each one. Buildertrend pushes schedule changes, subs send SMS, Andon classifies, API consumers read Red/Yellow status.

## Architectural Principle
- One API endpoint set for everything
- Authentication via API keys (per subscriber)
- Rate-limited, versioned (v1)
- All inputs go through the same InboundProcessor pipeline
- All outputs return the same card/status format regardless of source

## Endpoints (v1)

```
POST   /api/v1/events          — Push an inbound event (text, channel, sender)
GET    /api/v1/cards           — List active R/Y cards (with filters)
GET    /api/v1/cards/{id}      — Single card detail
POST   /api/v1/cards/{id}/resolve — Resolve a card
GET    /api/v1/schedule        — Current schedule (read from Buildertrend sync)
GET    /api/v1/status          — Health + metrics endpoint
```

## Integration: Buildertrend

- Read schedule from Buildertrend via their API
- When Buildertrend updates a schedule, Andon picks up the change
- When Andon classifies an issue, push status back to Buildertrend as a task/note
- Superintendent gets Red alerts without leaving Buildertrend

## Implementation Order

1. API key auth + rate limiting
2. `POST /api/v1/events` — core inbound pipeline exposed
3. `GET /api/v1/cards` — read current issues
4. `POST /api/v1/cards/{id}/resolve` — close issues remotely
5. Buildertrend webhook receiver (schedule changes)
6. Zapier connector (trigger: new Red card, action: create task)
