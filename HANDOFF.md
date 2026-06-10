# Handoff — 2026-06-10

## What Changed

#13 (Native reactive Qdrant) + #14 (bridge thread-offloading tests) — **DONE**. `QdrantFutures.toUni()` bridges `ListenableFuture` → Mutiny `Uni` via `Futures.addCallback` + `directExecutor` with cancellation propagation. `ReactiveQdrantCorpusStore` and `ReactiveHybridCaseRetriever` — native async Qdrant I/O, blocking ONNX embedding offloaded to worker pool. `ReactiveRagBeanProducer` (`@IfBuildProperty` + `@Startup` + `@PostConstruct` for `denseDimension` caching). `ensureCollection` uses `ConcurrentHashMap<String, Uni<Void>>` + `computeIfAbsent` + `memoize().indefinitely()` with failure eviction (verified from Mutiny source: memoize caches failures). Bridge thread-offloading tests on all 5 methods. Javadoc on reactive SPIs. Code review clean (#15 filed for deferred findings). ARC42STORIES.MD synced. Blog mdp05 published. Spec went through 6 review passes before implementation.

## Immediate Next Step

All planned work for `casehub-neural-text` is complete. Both #13 and #14 closed. Next action depends on consumer integration — likely `casehub-engine` for fact-space prompt compilation (parent#164).

## What's Left

- parent#214 — sync PLATFORM.md + neural-text deep-dive for reactive gating property · S · Low
- #15 — assertTenant Mutiny-idiomatic wrapping, delete-reingest test, StubEmbeddingModel extraction · S · Low
- 2 deferred forage entries (ConcurrentHashMap+memoize technique, @Startup on producer class undocumented) · XS · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #12 | Migrate Qdrant hybrid search to LangChain4j when #4994 ships | M | Low | Blocked on external LangChain4j PR |

## Key References

- ARC42STORIES.MD: C1–C7 ✅, J1+J2 ✅ — all chapters complete, L7 updated for reactive impls
- Spec: `specs/2026-06-09-native-reactive-qdrant-design.md` (workspace, 6 review passes)
- Blog: `blog/2026-06-10-mdp05-bridge-is-the-problem.md`
- Review findings: #15 (deferred minor items)
- Doc sync: parent#214 (updated with reactive details)
