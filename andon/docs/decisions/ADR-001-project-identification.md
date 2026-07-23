# ADR-001: Project Identification for Inbound Messages

**Date:** 2026-07-23
**Status:** Accepted
**Deciders:** Lead Architect, Product Owner

---

## Context

Inbound SMS, MMS, and Voice messages arrive from subcontractors who may be working on multiple active homes simultaneously. A sender's phone number combined with their trade is not sufficient to identify the correct project when a subcontractor is assigned to several houses — including multiple houses on the same street.

The system must reliably map each inbound message to the correct project without guessing.

## Decision

Implement a **Project Code** system with a defined resolution order.

### Project Code

Every project receives a unique, human-readable `project_code` (e.g., `LKV-01`, `LOT-14`, `001`). This code:
- Is unique within the company/tenant
- Is short enough to say or text
- Can be auto-generated and edited during onboarding
- Is displayed on issue cards alongside the address

### Resolution Order

Inbound messages are resolved against projects in this exact order:

1. **Exact project_code match** — highest confidence
2. **Exact full street_address match**
3. **Unique address fragment match** (e.g., "1234 Lakeview" matches only one project)
4. **Unique alias match** (lot number, subdivision nickname)
5. **Sender assigned to exactly one active project** via `project_contacts`
6. **Multiple candidates** → clarification requested from sender

### Clarification Workflow

When resolution produces multiple candidates:
1. The original message is stored with `clarification_status='pending'`
2. An SMS reply is sent listing the candidate projects
3. The sender replies with a number, project code, or address
4. The reply resolves the original message and resumes the pipeline
5. No second card is created from the clarification reply

### Rule: Never Guess

If resolution cannot determine the project with high confidence, the system must never guess. It must either clarify with the sender or place the message in manual review.

## Consequences

### Positive
- Reliable project routing for subs working multiple homes
- Self-service clarification without PM involvement
- Future-proof for multi-tenant use

### Negative
- Requires project codes during onboarding
- Requires outbound SMS credits for clarification replies
- Adds complexity to the inbound pipeline

## Pilot Limitations
- Voice clarification uses manual review (no automated outbound voice)
- Clarification is text-only (SMS replies)
- Existing houses (old pipeline) do not have project codes — will be backfilled as they're migrated