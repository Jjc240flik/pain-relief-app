# Future Feature: Zapier / Webhook Connector

**Source:** Vision Board — "hook into other contractor platforms"

## Goal
Let builders connect Andon to their existing toolchain without writing code. Zapier acts as the bridge: schedule changes from Buildertrend trigger Andon updates, new Red cards trigger Slack messages or Trello cards.

## Why
Most superintendents don't have an engineering team. Zapier lets them wire Andon into their workflow themselves. It also proves the API is useful before building deep native integrations.

## Triggers (when Andon sends data out)

- **New Red card** — a critical issue was created
- **New Yellow card** — a warning was created
- **Card resolved** — a Green status was set
- **Escalation fired** — a Red issue passed the time threshold

## Actions (when Andon receives data)

- **Create card** — push an event from another platform (e.g., email-to-SMS gateway)
- **Resolve card** — close an issue from a Slack command
- **Update schedule** — push schedule changes from Buildertrend

## Implementation

1. Expose the public API first (see `public_api.md`)
2. Add Zapier-specific REST endpoints with Zapier's expected payload format
3. Publish private Zapier app (or use Webhooks + Polling for MVP)
4. Provide template Zaps for common use cases:
   - "When a new Red card appears in Andon, send a Slack message to #ops"
   - "When Buildertrend updates a schedule, push to Andon"
   - "When a card is resolved in Andon, mark the task complete in Trello"
