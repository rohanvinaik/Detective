# Proposal

## Why

The published pair must expose the working local implementation while the remaining
repairs stay explicit and independently reviewable. Historical phase summaries mixed
implemented code, accepted obligations, performance claims and deferred additions.

## What Changes

- Record one cross-repository execution plan for B00–B12, with dependencies, retained
  obligations and acceptance evidence. Preserve the existing 89-issue queue.
- Record the 1.2.x dependency-floor correction, B02 implementation receipts, and the
  1.2.1 coverage/coexistence CI correction without marking entire packages accepted.
- Keep evidence-preserving cleanup separate from feature expansion, and retain every
  test whose removal cannot yet be warranted.
- Link release and issue status to actual commits, artifacts and measurements.

## Capabilities

### New Capabilities

None. This is a planning/documentation update for existing project contracts.

### Modified Capabilities

None. `skip_specs: true` applies to this documentation change: the theory and existing
issue acceptance criteria remain authoritative. Each later implementation change must
identify the existing obligation it repairs; a new promise needs its own proposal.

## Impact

Wesker and Detective are covered together; this planning home lives in Detective.
The historical [handoff](../../../docs/REPAIR_HANDOFF_2026-10-24.md) and
[issue queue](../../../docs/REPAIR_QUEUE_2026-10-24.json) remain the detailed basis.
The older SquishOS `consolidate-interpreter-monitoring` change is a related monitoring
subplan, not evidence that its old checked/unchecked statuses describe current code.
