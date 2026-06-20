# Handoff — 2026-06-20

## What Changed

Closed #38 and #41 on branch `issue-38-cursorstore-delete-reactive-crag`.

**#38 — CursorStore.delete()**: `void delete(String corpusName)` on the SPI with no default body. `FileCursorStore` deletes the `.cursor` file; `InMemoryCursorStore` removes from map. Unblocks Hortora engine#9 hybrid search migration (replaces `save(name, "")` workaround).

**#41 — ReactiveCorrectiveCaseRetriever**: CDI `@Decorator @Priority(100)` on `ReactiveCaseRetriever`, classpath-activated. Mutiny `Uni` chains with worker-thread offload for blocking `RelevanceEvaluator`. Uses `fireAsync()`. Already-graded guard prevents double CRAG when the blocking bridge is active — `RelevanceGrade.UNGRADED` as idempotency signal. `CragEvaluationLogic` shared helper extracted from blocking decorator (pure static functions, `GradeResult` record). Dedup key fixed from `content.hashCode()` to full content string. ARC42STORIES updated: C10, L10 marked ✅.

Spec: 3 review rounds, 12 findings. Critical: double CRAG through blocking-to-reactive bridge. Garden: GE-20260620-9d043b (CDI decorator double-application gotcha).

## Immediate Next Step

Pick from remaining backlog — all items are discretionary. Run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #40 | Consumer migration for CaseRetriever return type (CRAG) | S | Low | Cross-repo: casehub-engine + Hortora/engine |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy upgrade | L | High | R&D — triggered when cross-encoder thresholds insufficient |
| #29 | ColBERT late interaction retrieval — inference-colbert module | L | High | New retrieval mode, ONNX export + MaxSim scoring |
| #30 | BGE-M3 single-model multi-mode (dense + sparse + ColBERT) | L | High | Replaces separate embedding + SPLADE pipeline |
| #31 | Matryoshka embeddings + binary quantization for tiered search | M | Med | Qdrant already supports binary vectors |
| #32 | HyDE — hypothetical document embeddings for query expansion | S | Med | RAG-layer pre-retrieval stage |
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Spec: `specs/2026-06-20-cursorstore-delete-reactive-crag-design.md`
- Plan: `plans/attic/issue-38-cursorstore-delete-reactive-crag/2026-06-20-cursorstore-delete-reactive-crag.md`
- Garden: GE-20260620-9d043b
- Blog: `blog/2026-06-20-mdp14-guard-that-wasnt-obvious.md`
