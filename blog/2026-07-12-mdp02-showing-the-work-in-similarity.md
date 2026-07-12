---
title: "Showing the Work in Similarity"
date: 2026-07-12
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [cbr, similarity, scoring, explainability]
---

## Showing the Work in Similarity

CBR similarity scoring is a weighted sum across feature fields. A case scores 0.83 — but why? Which features drove it? Which dragged it down? Without per-feature contributions, the composite score is a black box.

`CbrSimilarityScorer` already computed per-feature similarities internally — it had to, for the weighted sum. The information existed in local variables and was immediately discarded. The fix was structural, not algorithmic: collect the per-feature contributions during the single scoring pass and return them alongside the composite score.

`SimilarityBreakdown` is a record that pairs the composite `score` with a `Map<String, Double>` of per-feature contributions. Each entry is the field's weighted contribution divided by the total weight — the fraction of the composite score attributable to that field. The values sum to the composite score. A consumer can look at the breakdown and immediately see that `economy: 0.31` carried the match while `difficulty: 0.02` contributed almost nothing.

The scorer gained `scoreDetailed()` returning the breakdown; `score()` delegates to it and extracts just the double. No performance cost — the breakdown is built from values already computed in the scoring loop.

`ScoredCbrCase` gained a `featureSimilarities` field (never null, empty map when unavailable). The in-memory store populates it from the breakdown. The Qdrant store populates it during client-side feature scoring in the two-pass hybrid retrieval. The cross-encoder reranking decorator preserves it through re-ranking — the feature-level breakdown from the original scoring pass survives even after the composite score is replaced by the cross-encoder's assessment.

The design keeps the contributions as raw weighted fractions, not re-normalized percentages. A field with weight 3.0 that matches perfectly contributes more than a field with weight 1.0 that also matches perfectly. The breakdown makes the weight configuration's effect visible — if tuning weights doesn't change outcomes, the breakdown shows why.
