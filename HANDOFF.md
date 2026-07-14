# Handoff — 2026-07-14

## What Changed

Branch `issue-85-cbr-plan-adaptation-spi` closed. Landed as `ad85141` on main. Closes #85 (CBR Phase 5 — plan adaptation SPI).

**Delivered:** `PlanAdapter` SPI in memory-api — the CBR Reuse phase. `AdaptedPlan`, `AdaptedStep` (with `AdaptationAction` enum: RETAINED/SUBSTITUTED/BOOSTED/SUPPRESSED/ADDED/REMOVED + reason), `AdaptationTrace` (with `retrievalTraceId` for retrieval-to-adaptation provenance), `CbrAdaptationRecorded` CDI event. `NoOpPlanAdapter` `@DefaultBean` in memory/ (zero behavioral change). `TrackingPlanAdapter` `@Decorator @Priority(50)` in memory-cbr-tracking (`casehub.cbr.adaptation-tracking.enabled`).

**Filed:** casehubio/engine#727 — wire PlanAdapter into CbrRetrievalService. casehubio/platform#174 — route CloudEvent types to CDI observers (unblocks neocortex#142).

## Immediate Next Step

Pick next from agreed sequencing. #64 (event-to-memory bridge) is independent and doesn't need the engine-side #727 to land first.

## Agreed Sequencing

1. ~~#140~~ — CBR Revise SPI — **done**
2. ~~#84~~ — Outcome learning + retrieval traceability — **done**
3. ~~#85~~ — Plan adaptation SPI — **done**
4. **#64** — Event-to-memory bridge (M/Med) — independent, next
5. **#88 remainder** — Trend detection + trajectory queries (L/High) — no consumer yet

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #147 | Decorator chain integration + double-recording guard @QuarkusTest | S | Low | Filed from #84 code review |
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |
| #148 | Cross-plan structural analysis | M | High | Filed during #85 design review |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #120 | Expansion drift metrics with auto-fallback | M | Med | |

## Key References

- Design spec: `docs/specs/2026-07-13-cbr-plan-adaptation-spi-design.md`
- Blog: `blog/2026-07-14-mdp01-the-missing-phase.md`
