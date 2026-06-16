# Handoff — 2026-06-17

## What Changed

Closed #34 — replaced `@Scheduled` polling in `CorpusIngestionService` with event-driven filesystem watching via `gmethvin/directory-watcher`. New `WatchableChangeSource` SPI in `corpus-api`. `FlatChangeSource` and `CompositeChangeSource` implement it. Service uses hybrid model: event-driven for filesystem corpora, polling fallback for ZIP-based. Also added examples modules to default pom.xml build, created 5 new feature issues (#29–#33: ColBERT, BGE-M3, Matryoshka, HyDE, CRAG), and fixed Podman/Testcontainers socket configuration.

## Immediate Next Step

Pick from remaining backlog — all items are discretionary, none urgent. Run `/work` to start.

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

- Garden: `GE-20260616-fd338a` (FSEvents catch-up), `GE-20260616-bb6aac` (fileHashing DELETE), `GE-20260616-bb45d5` (Podman Testcontainers)
