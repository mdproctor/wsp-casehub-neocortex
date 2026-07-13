*Updated: #131, #137 closed — removed from backlog.*

# Handoff — 2026-07-13

## What Changed

Branch `issue-137-approx-dtw-typed-cbr` closed. Landed as `722674c` on main. Covers #131 (typed CBR feature values) and #137 (approximate DTW). Both issues closed.

**Delivered:** Sealed `FeatureValue` hierarchy (7 variants) replaces `Map<String, Object>` across all CBR APIs — memory-api, contract tests, Qdrant backend, embedding similarity, cross-encoder tests, and all CBR example demos. LbKeogh O(n) lower-bound pruning + DtwSimilarity early abandonment integrated into InMemoryCbrCaseMemoryStore retrieval loop for SakoeChibaBand DTW optimization.

**Known limitation:** `CbrPointBuilder.fromRawMap()` defaults empty JSON lists to `StringListVal`. Schema-aware reconstruction would handle empty TimeSeries/NumberList correctly but isn't triggered by current tests.

## Immediate Next Step

Pick next issue from backlog. Cross-repo issue for engine needed: `CbrRetrievalService.mapScoredCase()` uses `c.features()` and needs updating for FeatureValue (deferred from Task 6 — file manually).

## What's Next — CBR App Enablement Critical Path

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #84 | Outcome learning + retrieval traceability | L | High | Unblocked — track C head |
| #85 | Plan adaptation SPI | M | High | Blocked by #84 |

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #120 | Expansion drift metrics with auto-fallback | M | Med | |

## Key References

- Spec: `docs/specs/2026-07-12-typed-features-and-approx-dtw-design.md`
- Plan: workspace `plans/attic/issue-137-approx-dtw-typed-cbr/2026-07-12-typed-features-and-approx-dtw.md`
- Blog: `blog/2026-07-12-mdp03-the-type-that-replaced-object.md`
