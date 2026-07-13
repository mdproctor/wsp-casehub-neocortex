# Handoff — 2026-07-13

## What Changed

Branch `issue-140-cbr-revise-spi` closed. Landed as `8863054` on main. Closes #140 (CBR Revise SPI).

**Delivered:** `CbrOutcome` record with EMA confidence adjustment. `recordOutcome(caseId, tenantId, outcome)` on `CbrCaseMemoryStore` + reactive parity. All 6 implementations (NoOp, InMemory, Qdrant, JPA, reranking decorators, bridge). 9 contract tests. JPA V2 migration (outcome_detail, last_outcome_at). `CbrOutcomeConsumer` CloudEvent bridge in memory/ module. `casehub-desiredstate-api` dependency added.

Also closed: #132–#136 (typed feature children of #131, all delivered previously). #86 (capability tiers epic, all children done).

**Follow-on filed:** #142 — wire CbrOutcomeConsumer to platform CloudEvent routing (Ganglion/RAS).

## Immediate Next Step

Pick next from agreed sequencing. #84 (outcome learning + retrieval traceability) builds directly on #140's `recordOutcome` infrastructure.

## Agreed Sequencing

1. ~~#140~~ — CBR Revise SPI — **done**
2. **#84** — Outcome learning + retrieval traceability (L/High) — next
3. **#85** — Plan adaptation SPI (M/High) — blocked by #84
4. **#64** — Event-to-memory bridge (M/Med) — independent
5. **#88 remainder** — Trend detection + trajectory queries (L/High) — no consumer yet

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform event adapter |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #120 | Expansion drift metrics with auto-fallback | M | Med | |

## Key References

- Design spec: `docs/specs/2026-07-13-cbr-revise-spi-design.md`
- Plan: workspace `plans/attic/issue-140-cbr-revise-spi/2026-07-13-cbr-revise-spi.md`
