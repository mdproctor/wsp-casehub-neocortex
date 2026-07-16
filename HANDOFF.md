# Handoff — 2026-07-16

## What Changed

Branch `issue-93-cbr-hierarchical-scoping` closed. Landed as `ceb6d45` on main. PR casehubio/neocortex#156. Closes #152.

**Delivered:** CBR active memory management — temporal decay decorator @Priority(80) with Linear/Step variants, supersession SPI (supersede/reinstate with audit metadata). ScoredCbrCase gains `Instant storedAt` + `with*()` immutable copy methods; all decorators migrated. Store-level decay removed from InMemory/JPA (decorator is the single point). Dead code `toFilter()` deleted. Design review: 3 rounds, 16 issues, all resolved ($11.48).

**Key design decisions:** Decay as decorator not store-level (store-level is discarded by reranking cross-encoder). `storedAt` is domain data not storage leakage. Supersession as store-level filter not decorator. Case compaction deferred (GDPR Art.17 entity decomposition problem).

**Epic structure:** #93 decomposed into 3 child issues — #152 (done), #153 (hierarchical scoping, pending), #154 (trust-weighted retention, blocked by platform trust infra).

## Immediate Next Step

Pick next from backlog. #153 (hierarchical scoping) is the next Phase 7 sub-phase. #148 (cross-plan structural analysis) is the next substantial CBR work outside Phase 7.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #153 | Hierarchical scoping — scope hierarchy, scope-aware retrieval, GDPR isolation | L | High | Phase 7 sub-phase 2 |
| #154 | Trust-weighted retention — precedent authority + trust trajectory | S | Med | Blocked by platform trust infra |
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | Deferred from #85 |
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |

## References

- Spec: `docs/specs/2026-07-15-cbr-active-memory-management-design.md`
- Plan: `docs/plans/2026-07-15-cbr-active-memory-management.md`
- Garden: GE-20260716-f292d3 (score-replacing decorator gotcha)
