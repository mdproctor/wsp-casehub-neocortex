# Handoff — 2026-07-05

## What Changed

Closed 6 issues in a single branch (#104, #51, #52, #61, #82, #87). OnnxInferenceModel input name alias resolution (static alias table + ModelConfig overrides). SparseEmbedder rank-3 max-pool reduction. SeparateModelEmbedder adapter bridging LangChain4j EmbeddingModel + optional SparseEmbedder into MultiModalEmbedder, with @DefaultBean CDI producer displaced by BgeM3. Configurable fusion strategy (RRF/DBSF server-side, CC client-side with per-leg weights and min-max normalization). CBR weighted similarity — CbrSimilarityScorer with per-field local similarity functions (categorical exact match, numeric linear decay, text exact match), configurable per-field weights on CbrQuery, features moved from hard Qdrant payload filters to client-side graded scoring. Landed on upstream main as `a32d098`. Filed 3 deferred issues (#106, #107, #108) and 1 doc-sync issue (parent#350).

## Immediate Next Step

All 6 issues closed. Pick from What's Next — #63 (embedding evaluation) is the next substantive piece. #65 (Memori adapter) is blocked on external dependency.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #106 | Semantic text field similarity in CbrSimilarityScorer | M | Med | Deferred from #82/#87 |
| #107 | Categorical similarity tables | M | Med | Deferred from #82/#87 |
| #108 | Per-field similarity function configuration | S | Low | Deferred from #82/#87 |

## Key References

- Design spec: `specs/2026-07-05-batch-inference-fusion-cbr-design.md` (workspace)
- Plan: `plans/attic/issue-104-batch-fusion-inference-cbr/2026-07-05-batch-inference-fusion-cbr.md` (workspace)
- Design review: `~/adr/casehub-neocortex/batch-inference-fusion-cbr-20260705-144443/`
- Blog: `blog/2026-07-05-mdp02-features-are-not-filters.md` (workspace)
- Garden: `GE-20260705-b59012` — Qdrant Formula cannot reference prefetch leg scores
