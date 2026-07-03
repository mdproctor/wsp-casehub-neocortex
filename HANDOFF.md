# Handoff — 2026-07-03

## What Changed

Closed 4 issues under epic #68 (CBR production readiness). Dense vector search (#70) — `CbrQuery.problem` field for query-side embedding, dual-path `searchAsync`/`scrollAsync` in `QdrantCbrCaseMemoryStore`, `ScoredCbrCase<C>` return type (breaking API change surfaced by design review). minSimilarity (#71) wired to Qdrant `score_threshold`. Parent CBR spec (#58) synced with all implementation changes. #59 closed as already resolved — discriminator-based switch was in place.

Design review ran 4 rounds ($15.95), caught `ScoredCbrCase` return type gap and score_threshold semantics. Final code review: 0 critical, 1 important (#78 filed), 4 minor (#79 filed).

Garden entry: `GE-20260703-39256d` — Qdrant `score_threshold=0.0` vs omitted semantics.

Landed on main as `5d02e6b`.

## Immediate Next Step

#74 (reconciliation job) is the next M-sized issue — needed for automated recovery from dimension migration and Qdrant index consistency. Dense vector search makes this more pressing since collection recreation drops existing points.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on Memori shipping stable REST API
- #74 — Reconciliation job — reindex + orphan cleanup · M · Med
- #78 — Gate destructive dimension-mismatch recovery behind config flag · S · Low · blocked by #74
- #79 — Minor findings: ScoredCbrCase docs/validation, Qdrant test gap, duplicate effectiveDim · XS · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #74 | Reconciliation job | M | Med | Not blocking initial rollout but needed for dim migration |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #78 | Dimension migration config gate | S | Low | Blocked by #74 |
| #79 | Minor review findings batch | XS | Low | Non-blocking cleanup |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |

## Key References

- Garden entry: `GE-20260703-39256d` — Qdrant score_threshold semantics
- Garden entry: `GE-20260703-885029` — Qdrant ValueFactory.value(long) creates IntegerValue
- Epic: casehubio/neocortex#68
- Design review: `~/adr/casehub-neocortex/cbr-dense-vector-search-20260703-191234/`
