# Handoff — 2026-06-18

## What Changed

Closed #33 — Corrective RAG (CRAG). New `rag-crag` module: CDI `@Decorator` on `CaseRetriever` that evaluates retrieval quality via `RelevanceEvaluator` SPI, filters INCORRECT chunks, expands search when too few survive, fires `RetrievalQuality` CDI events. Default `CrossEncoderRelevanceEvaluator` — threshold-based grading reusing deployed cross-encoder. `rag-api` enriched with `RelevanceGrade`, `RetrievalQuality`, and graded `RetrievedChunk`. `InMemoryRelevanceEvaluator` stub in `rag-testing`. ARC42STORIES: J4, C10, L10. Three rounds of spec review refined the design: CDI `@Decorator` (not `@Alternative`), `List<RetrievedChunk>` return type (not `RetrievalResult` wrapper), CDI event for quality metadata, constructor injection for testability.

Filed: #39 (dedicated evaluator model), #40 (consumer adoption), #41 (reactive decorator), parent#286 (PLATFORM.MD update). Garden: GE-20260618-fe1853 (float-to-double threshold comparison), GE-20260618-d84391 (CDI decorator testing technique).

## Immediate Next Step

Pick from remaining backlog — all items are discretionary. Run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #41 | ReactiveCorrectiveCaseRetriever — reactive path CRAG | S | Med | Verify @IfBuildProperty + @Decorator composition in Quarkus Arc |
| #29 | ColBERT late interaction retrieval — inference-colbert module | L | High | New retrieval mode, ONNX export + MaxSim scoring |
| #30 | BGE-M3 single-model multi-mode (dense + sparse + ColBERT) | L | High | Replaces separate embedding + SPLADE pipeline |
| #31 | Matryoshka embeddings + binary quantization for tiered search | M | Med | Qdrant already supports binary vectors |
| #32 | HyDE — hypothetical document embeddings for query expansion | S | Med | RAG-layer pre-retrieval stage |
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Spec: `specs/2026-06-18-corrective-rag-crag-design.md`
- Plan: `plans/attic/issue-33-corrective-rag-crag/2026-06-18-corrective-rag-crag.md`
- Garden: GE-20260618-fe1853, GE-20260618-d84391
