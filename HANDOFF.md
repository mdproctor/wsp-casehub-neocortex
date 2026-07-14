# Handoff — 2026-07-14

## What Changed

Branch `issue-149-cbr-small-fixes` closed. Landed as `23d58f8` on main. Closes #149, #147, #150, #151.

**Delivered:** Four CBR small fixes batched on one branch — FeatureValue.of() Boolean support (#149), CbrRetentionPolicy + purge() SPI with InMemory/JPA/Qdrant implementations (#150), TemporalDecay sealed interface with HalfLife on CbrQuery applied in InMemory/JPA stores (#151), decorator chain integration test verifying tracking captures post-weighted scores and BridgedCbrStore double-recording guard (#147).

**Garden:** GE-20260714-85bd9a — Qdrant scrollAsync returns unmodifiable protobuf list gotcha.

## Immediate Next Step

Pick next from agreed sequencing or backlog. #88 (temporal trajectory CBR) is next in the agreed sequence but L/High with no consumer yet. #142 (wire CbrOutcomeConsumer) still blocked by platform#174.

## Agreed Sequencing

1. ~~#140~~ — CBR Revise SPI — **done**
2. ~~#84~~ — Outcome learning + retrieval traceability — **done**
3. ~~#85~~ — Plan adaptation SPI — **done**
4. ~~#64~~ — Event-to-memory bridge — **done**
5. **#88 remainder** — Trend detection + trajectory queries (L/High) — no consumer yet

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |
| #148 | Cross-plan structural analysis | M | High | Filed during #85 design review |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
