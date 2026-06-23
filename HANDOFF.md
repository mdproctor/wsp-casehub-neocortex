# Handoff — 2026-06-23

## What Changed

Closed #32 on branch `issue-32-hyde-query-expansion`.

**#32 — HyDE query expansion**: `RetrievalQuery` value type replaces `String query` in `CaseRetriever`/`ReactiveCaseRetriever` SPIs — separates embedding text (`searchText()`) from scoring text (`text()`). New `QueryExpander` SPI in `rag-api`. New `rag-hyde` module: `HydeCaseRetriever`/`ReactiveHydeCaseRetriever` CDI `@Decorator @Priority(200)` with fail-safe error handling; `LlmQueryExpander` (ChatModel-backed) and `TemplateQueryExpander` (pattern-based) implementations. Dense embedding uses `searchText()`, sparse SPLADE uses `text()`, reranking uses `text()`. Classpath + config activated (`casehub.rag.hyde.enabled=true`). CRAG retrofitted to classpath + config activation (`casehub.rag.crag.enabled=true`) — all three beans gated by `@IfBuildProperty`. ARC42STORIES updated: C11, L11. Out-of-scope items filed: #42 (multi-query HyDE), #43 (step-back prompting).

Spec: 3 review rounds, all findings resolved. Garden: ChatModel lambda gotcha already covered by GE-20260525-fd4868. Blog: mdp15.

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
| #42 | Multi-query HyDE — generate N hypothetical documents | M | Med | Enhancement to #32 |
| #43 | Step-back prompting QueryExpander | S | Med | New QueryExpander implementation |
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Spec: `specs/2026-06-21-hyde-query-expansion-design.md`
- Plan: `plans/attic/issue-32-hyde-query-expansion/2026-06-22-hyde-query-expansion.md`
- Blog: `blog/2026-06-23-mdp15-string-that-did-three-jobs.md`
