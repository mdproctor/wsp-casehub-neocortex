# Handoff — 2026-06-09

## What Changed

#11 (Reactive CorpusStore + CaseRetriever) — **DONE**. Reactive SPI interfaces in `rag-api` (Mutiny `provided` — ledger-api/eidos-api pattern), `@DefaultBean` bridges in `rag` (wraps blocking delegates on worker pool), in-memory reactive stubs in `rag-testing` (`@Alternative @Priority(1) @ApplicationScoped`, no `@IfBuildProperty`). Parity ArchUnit test. Fixed pre-existing `@ApplicationScoped` gap on blocking stubs. Filed protocol update issues (parent#213, garden#3) — module-tier-structure says Mutiny excluded from Tier 1 but two canonical repos already do it. ARC42STORIES.MD synced (C7 ✅, L6/L7 completed + gotchas + patterns populated, J1+J2 ✅). Blog published (mdp05).

## Immediate Next Step

All planned work for `casehub-neural-text` is complete. Both journeys done (C1–C7 ✅). Next action depends on consumer integration — likely `casehub-engine` for fact-space prompt compilation (parent#164).

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #13 | Native reactive Qdrant implementations (ReactiveQdrantCorpusStore, ReactiveHybridCaseRetriever) | M | Med | ListenableFuture → Mutiny bridge; discretionary — bridges provide functional baseline |
| #14 | Bridge thread-offloading regression test + minor findings | S | Low | Platform-wide gap, not blocking |
| #12 | Migrate Qdrant hybrid search to LangChain4j when #4994 ships | M | Low | Blocked on external LangChain4j PR |

## Key References

- ARC42STORIES.MD: C1–C7 ✅, J1+J2 ✅ — all chapters complete
- Spec: `docs/specs/2026-06-09-reactive-rag-spis-design.md`
- Blog: `blog/2026-06-09-mdp05-protocol-vs-codebase.md`
- Protocol issues: parent#213, garden#3 (Mutiny in Tier 1)
- Doc sync issue: parent#214 (PLATFORM.md + deep-dive)
