# Handoff — 2026-07-08

## What Changed

Closed #83 (CBR Phase 3 — semantic case retrieval). Hybrid two-pass retrieval in `QdrantCbrCaseMemoryStore` with mode dispatch (`RetrievalMode.FEATURE_ONLY`, `SEMANTIC_ONLY`, `HYBRID`) and configurable fusion (`CbrFusionStrategy.RRF`, `CC`). `ScoreFusion` utility in `memory-api` provides generic RRF and CC algorithms — domain-neutral, shared by CBR and future RAG consolidation (#124). New `memory-cbr-crossencoder` module: `@Decorator @Priority(75)` on `CbrCaseMemoryStore` + `ReactiveCbrCaseMemoryStore`, sigmoid-normalized cross-encoder scores, classpath + config activated (`casehub.cbr.reranking.enabled`). `ScoredCbrCase.reranked` field for double-reranking guard. `CbrSimilarityScorer.compositeScore()` removed — superseded by `ScoreFusion`. Auto-degradation when prerequisites absent (HYBRID → FEATURE_ONLY, SEMANTIC_ONLY → empty). Contract tests for retrieval modes across all implementations. Design review: 5 rounds, 20 issues, 18 verified, 2 accepted ($20.50). Landed as `14e883f` on both `origin/main` and `upstream/main`.

## Issues Filed

- #122 — Sparse embeddings (SPLADE) for CBR
- #123 — BM25 leg for CBR
- #124 — RrfFusion → ScoreFusion consolidation (RAG callers)

## Garden Entries

- GE-20260708-9213d2 — Ranked fusion ID extraction must use storage-level unique IDs

## Immediate Next Step

Pick next work item from What's Next — #122, #123, #124 are new; #109 and #120 remain unblocked.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low

## What's Next — CBR App Enablement Critical Path

Three parallel tracks — all converge to make CBR usable across casehub apps:

```
Track A (retrieval quality):  #124 → #123 → #122
Track B (case richness):      #89 → #91 → #92
Track C (compliance):         #84 → #85
```

| # | Description | Scale | Complexity | Track | Blocked by | Unlocks |
|---|-------------|-------|------------|-------|------------|---------|
| #124 | ScoreFusion consolidation (RAG callers) | S | Low | A | — | #123, #122 |
| #123 | BM25 leg for CBR | S | Low | A | #124 | #122 |
| #122 | SPLADE sparse embeddings for CBR | M | Med | A | #124 | — |
| #89 | Structured case fields (nested objects, list containment) | M | Med | B | — | #91 |
| #91 | Temporal case representation (time-series segments) | M | High | B | #89 | #92 |
| #92 | Sequence similarity (DTW, edit distance) | M | High | B | #91 | — |
| #84 | Outcome learning + retrieval traceability | L | High | C | — | #85; gates regulated apps |
| #85 | Plan adaptation SPI | M | High | C | #84 | — |

**Recommended start:** #124 + #89 + #84 in parallel (all three track heads are unblocked).

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked (#105 closed) |
| #120 | Expansion drift metrics with auto-fallback | M | Med | Builds on per-leg embedding + score propagation |

## Key References

- Spec: `docs/specs/2026-07-08-cbr-semantic-retrieval-design.md`
- Garden: `GE-20260708-9213d2` (fusion ID extraction gotcha)
