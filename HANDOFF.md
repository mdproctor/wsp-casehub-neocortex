# Handoff — 2026-06-30

## What Changed

Closed `issue-53-payload-hardening-bm25` — #53 (camelCase tokenization), #54 (metadata key collision), #48 (BM25 third RRF leg). Server-side BM25 sparse vectors via Qdrant `Document` inference with `Modifier.Idf` — not the filter-based approach from the original #48 description. Two-layer metadata validation: `ChunkInput` rejects field-name shadows at API tier, `QdrantPointBuilder` rejects `tenantId` at impl tier. `CamelCaseExpander` splits identifiers for BM25 only (SPLADE uses WordPiece). Constructor redesign: `RagConfig` passed directly, replacing 15+ individual parameters. Design review (4 rounds, 12 issues). 1 garden entry (GE-20260629-114162 — Qdrant Java client BM25 API underdocumented).

## Immediate Next Step

Pick from backlog — run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #46 | SPLADE/reranker tuning for garden retrieval | ? | ? | Blocked on Hortora/engine#28 |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |
| #30 | BGE-M3 single-model multi-mode | L | High | Replaces separate embedding + SPLADE |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred until second consumer |
| #20 | CaseRetriever CBR contract | L | High | Depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on LangChain4j #4994 |

## Key References

- Design spec: `docs/specs/issue-53-payload-hardening-bm25/2026-06-29-payload-hardening-bm25-design.md` (project)
- Garden: GE-20260629-114162 (Qdrant Java client BM25 API underdocumented)
- Blog: `blog/2026-06-30-mdp01-three-legs-flat-namespace.md`
