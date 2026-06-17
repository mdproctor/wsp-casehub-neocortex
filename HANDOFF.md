# Handoff — 2026-06-17

## What Changed

Closed #35 — made rag modules consumable by Hortora engine. Three gaps closed: (1) `PayloadFilter` sealed algebra (Eq, In, Not, And, Or) in `rag-api` with query-time payload filtering on `CaseRetriever`/`ReactiveCaseRetriever`, (2) optional `SparseEmbedder` via `Instance<>` for dense-only mode, (3) deterministic point IDs from `sourceDocumentId` + per-document chunk index. Cross-repo issues filed: casehubio/engine#521 (CaseRetriever call-site update), casehubio/parent#270 (PLATFORM.md dependency map). Spec went through 3 rounds of Hortora engine review.

## Immediate Next Step

Pick from remaining backlog — all items are discretionary. Run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #29 | ColBERT late interaction retrieval — inference-colbert module | L | High | New retrieval mode, ONNX export + MaxSim scoring |
| #30 | BGE-M3 single-model multi-mode (dense + sparse + ColBERT) | L | High | Replaces separate embedding + SPLADE pipeline |
| #31 | Matryoshka embeddings + binary quantization for tiered search | M | Med | Qdrant already supports binary vectors |
| #32 | HyDE — hypothetical document embeddings for query expansion | S | Med | RAG-layer pre-retrieval stage |
| #33 | Corrective RAG (CRAG) — self-healing retrieval | M | Med | Lightweight evaluator model on ONNX |
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Spec: `specs/2026-06-17-rag-hortora-shared-code-gaps-design.md`
- Plan: `plans/attic/issue-35-rag-hortora-gaps/2026-06-17-rag-hortora-gaps.md`
- Cross-repo: casehubio/engine#521, casehubio/parent#270
- ARC42STORIES: §2 constraint needs updating (Hortora now consumes rag-* modules)
