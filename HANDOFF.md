# Handoff — 2026-07-12

## What Changed

Closed #92 (sequence similarity refinements). Four capabilities added to `memory-api`: (1) DTW alignment path extraction via cost-matrix backtracing — `DtwResult` with `List<AlignmentPair>`, (2) Sakoe-Chiba windowed DTW via `DtwSpec(Integer windowSize)` on `SimilaritySpec`, (3) weighted edit distance with domain-specific substitution costs via `EditDistanceSpec(Map substitutionSimilarities)` on `SimilaritySpec`, (4) `EditStep` with explicit `EditOp` tagging (MATCH/SUBSTITUTE/INSERT/DELETE) and `-1` sentinel for uninvolved indices. `TimeSeries` and `DiscreteSequence` gain optional `SimilaritySpec` fields following the pattern `Categorical` and `Numeric` already use. Shared `validateAndMirrorSimilarityMap` with NaN rejection fix (pre-existing bug in `CategoricalTable`). Design review: 4 rounds, 14 issues, 10 verified, 4 accepted ($14). Landed as `47abc3c` on both `origin/main` and `upstream/main`. Filed deferred issues #137 (approximate DTW), #138 (Itakura parallelogram), #139 (insert/delete costs).

## Immediate Next Step

Pick next work item from What's Next. Track B is now complete (#91 + #92 delivered). Track C head (#84 outcome learning) is unblocked.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low
- #129 — ARC42 CBR module documentation (§5 Building Block View) · M · Low

## What's Next — CBR App Enablement Critical Path

Track A complete. Track B complete (#91 + #92 delivered).

| # | Description | Scale | Complexity | Track | Notes |
|---|-------------|-------|------------|-------|-------|
| #84 | Outcome learning + retrieval traceability | L | High | C | Unblocked — track C head |
| #85 | Plan adaptation SPI | M | High | C | Blocked by #84 |

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #131 | Typed CBR feature values (epic) | L | High | Design first (#132), then flat → structured → temporal → integration |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #120 | Expansion drift metrics with auto-fallback | M | Med | |
| #125 | NumericList field type | S | Low | Deferred from #89 |
| #126 | NotContains / NotContainsAny filters | S | Low | Deferred from #89 |
| #127 | Compound same-field filters (AllOf) | S | Low | Deferred from #89 |
| #137 | Approximate DTW (LB_Keogh + early abandonment) | S | Med | Deferred from #92 |
| #138 | Itakura parallelogram constraint | S | Low | Deferred from #92 |
| #139 | Configurable insert/delete costs | S | Low | Deferred from #92 |

## Key References

- Spec: `docs/specs/2026-07-11-sequence-similarity-refinements-design.md`
- Review: `~/adr/casehub-neocortex/sequence-similarity-refinements-20260711-185641/`
- Garden: `GE-20260711-604219` (IntelliJ MCP compact constructor gotcha)
