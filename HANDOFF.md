# Handoff — 2026-07-06

## What Changed

Delivered #106: pluggable per-field similarity in `CbrSimilarityScorer`. `LocalSimilarityFunction` SPI in `memory-api` (Tier 1, pure Java). `FeatureField.Text` gains `semantic` flag — opt-in via `semanticText()` factory, default `false`. New `memory-cbr-embedding` module with `EmbeddingTextSimilarity` (batch `precompute()` via `embedAll()`, cache-backed `compute()`, cosine similarity clamped to [0,1]). `QdrantCbrCaseMemoryStore` restructured to two-pass flow: reconstruct all candidates → batch precompute embeddings → score with warm cache. Contract test extended with Text field (28 tests). Design review (5 rounds, 13 issues, all resolved, $17.35). Landed on upstream main as `0e33ca0`.

## Immediate Next Step

Pick from What's Next. #107 and #108 now use the same `LocalSimilarityFunction` override map — no mechanism changes needed, just new function implementations.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #107 | Categorical similarity tables | M | Med | Same LocalSimilarityFunction mechanism |
| #108 | Per-field similarity function configuration | S | Low | Config layer populating overrides map |
| #109 | Retrieval tracking analysis service | M | Med | Depends on #105 (closed) |
| #110 | Retrieval tracking data retention policy | S | Low | Depends on #105 (closed) |

## Key References

- Spec: `docs/specs/2026-07-06-semantic-text-similarity-design.md` (project)
- Design review: `~/adr/casehub-neocortex/semantic-text-similarity-20260706-140322/`
- Plan: `plans/2026-07-06-semantic-text-similarity.md` (workspace)
