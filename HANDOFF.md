# Handoff — 2026-07-17

## What Changed

Branch `issue-153-cbr-hierarchical-scoping` closed. Landed as `912c540` on main. Closes #153.

**Delivered:** CBR hierarchical scoping — `ScopeDecay` sealed interface (Exponential, Linear, Step), scope-aware retrieval using platform `Path` (`io.casehub.platform.api.path.Path`), store-level visibility filtering (`isAncestorOf`), `ScopeDecayCbrCaseMemoryStore` @Decorator @Priority(85). SPI break: `store()` gains `Path scope`, `CbrQuery` gains `scope` + `scopeDecay`, `ScoredCbrCase` gains `scope`. All store implementations updated (InMemory, JPA + Flyway V4, Qdrant + ancestor `matchKeywords`). All decorators forwarding scope. Design review: 3 rounds, 9 issues, all verified ($12.54).

**Key design decisions:** Scope orthogonal to domain (not a replacement). Platform Path for hierarchy (no custom ScopeLevel enum). Blended retrieval with decorator-based decay (not store-level). Aggregates are regular cases (no aggregation SPI). GDPR erasure stays entity-anchored.

**Epic structure:** #93 Phase 7 sub-phase 2 complete. #154 (trust-weighted retention) remains — blocked by platform trust infra.

## Immediate Next Step

Pick next from backlog. #148 (cross-plan structural analysis) is the next substantial CBR work. #154 blocked.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #154 | Trust-weighted retention — precedent authority + trust trajectory | S | Med | Blocked by platform trust infra |
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | Deferred from #85 |
| #158 | Scope-based bulk erasure — eraseByScope(Path, tenantId) | S | Low | Depends on #153 (done) |
| #159 | Aggregate adjustment on entity erasure — reactive notification | S | Med | Depends on #153 (done) |
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |

## References

- Spec: `docs/specs/2026-07-16-cbr-hierarchical-scoping-design.md`
- Plan: `docs/plans/2026-07-17-cbr-hierarchical-scoping.md`
- Garden: GE-20260716-f292d3 (score-replacing decorator gotcha)
