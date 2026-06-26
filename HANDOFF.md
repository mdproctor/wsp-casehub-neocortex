# Handoff — 2026-06-26

## What Changed

Closed `issue-26-embedall-batching` — hortora/engine#26 (embedAll batching). `QdrantEmbeddingIngestor` and `ReactiveQdrantEmbeddingIngestor` now batch `embedAll`/`embedBatch`/`upsertAsync` into configurable windows (default 100, via `casehub.rag.embedding-batch-size`). Fixes 400 Bad Request from Ollama on ~6,500-entry garden corpus.

Extracted `QdrantPointBuilder` — shared `buildPoint()` + `computeChunkIndices()` utility, eliminating duplication between blocking and reactive implementations. Pre-computed chunk indices ensure deterministic UUIDs are batch-size-independent.

Also verified: `@QuarkusMain` removal (cf7f381) survived the issue-43 merge.

## Immediate Next Step

Pick from backlog — run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #45 | Parallel LLM calls for multi-query HyDE | S | Med | Blocked on async ChatModel API |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |
| #30 | BGE-M3 single-model multi-mode | L | High | Replaces separate embedding + SPLADE |
| #31 | Matryoshka embeddings + binary quantization | M | Med | Qdrant supports binary vectors |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred until second consumer |
| #20 | CaseRetriever CBR contract | L | High | Depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on LangChain4j #4994 |

## Key References

- Spec: `docs/specs/2026-06-25-embedall-batching-design.md`
- Blog: `blog/2026-06-26-mdp18-embedall-batching.md`
- Garden: `jvm/GE-20260626-25963a.md`
