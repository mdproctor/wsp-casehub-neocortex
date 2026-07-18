# Handoff — 2026-07-18

## What Changed

Branch `issue-101-reactive-native-backends` closed. Landed as `321e81f` on main. Pushed to both origin (mdproctor/neocortex) and upstream (casehubio/neocortex). Closes #101.

**Delivered:** Native reactive backends for all non-JDBC memory stores. Canonical direction follows the underlying technology (engine pattern): blocking-canonical for in-memory (ConcurrentHashMap), reactive-canonical for REST/gRPC backends. `ReactiveGraphCaseMemoryStore` interface added to memory-api. 21 files changed, 2807 insertions, 1796 deletions.

| Backend | Canonical | New classes |
|---------|-----------|-------------|
| In-memory | Blocking | `ReactiveInMemoryMemoryStore`, `ReactiveInMemoryCbrCaseMemoryStore` |
| Mem0 | Reactive | `ReactiveMem0Client`, `ReactiveMem0CaseMemoryStore` |
| Graphiti | Reactive | `ReactiveGraphitiClient`, `ReactiveGraphitiCaseMemoryStore` |
| Qdrant | Reactive | `ReactiveQdrantCbrCaseMemoryStore` (parallel search legs, async gRPC) |

Design review: 3 rounds, 18 issues, 16 verified. Code review: 1 CRITICAL fixed (event-loop blocking in store/registerSchema). Follow-up: #165 (CbrCollectionManager async methods).

## Immediate Next Step

Pick next from backlog. #165 is a small follow-up to complete the async migration in CbrCollectionManager.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #165 | CbrCollectionManager async methods | S | Low | Follow-up from #101 |
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | Deferred from #85 |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |
| #154 | Trust-weighted retention — precedent authority + trust trajectory | S | Med | Blocked by platform trust infra |
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |

## References

- Spec: `docs/specs/2026-07-18-native-reactive-backends-design.md`
- Plan: `plans/2026-07-18-native-reactive-backends.md` (workspace)
- Garden: GE-20260616-bdde66 revised — Mutiny Uni conversion for ListenableFuture
- Issue filed: #165 (CbrCollectionManager async methods)
