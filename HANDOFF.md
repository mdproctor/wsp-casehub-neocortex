# Handoff — 2026-07-12

## What Changed

Closed #125, #126, #127, #138, #139 (CBR enhancements batch). Five capabilities added to `memory-api`: (1) `WarpingConstraint` sealed interface with `Unconstrained`, `SakoeChibaBand`, `ItakuraParallelogram` — replaces `DtwSpec(Integer windowSize)` with non-null `DtwSpec(WarpingConstraint constraint)`, Itakura infeasibility detection inside DP loop. (2) Configurable insert/delete costs on `EditDistanceSpec` — variable-cost DP with correct normalization for both sub-preferred and del+ins-preferred regimes. (3) `FeatureField.NumericList(name, min, max)` filter-only field type + `CbrFilter.ContainsRange(NumericRange)` for numeric array containment. (4) `CbrFilter.NotContains` / `NotContainsAny` negation filters for CategoricalList. (5) `CbrFilter.AllOf(List<CbrFilter>)` compound same-field filter with polarity-preserving Qdrant dispatch. Design review: 2 rounds, 9 issues, all verified. Landed as `4422db0` on both `origin/main` and `upstream/main`.

## Immediate Next Step

Pick next work item from What's Next. Track C head (#84 outcome learning) is unblocked.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low
- #129 — ARC42 CBR module documentation (§5 Building Block View) · M · Low

## What's Next — CBR App Enablement Critical Path

Track A complete. Track B complete.

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
| #137 | Approximate DTW (LB_Keogh + early abandonment) | S | Med | Deferred from #92 |

## Key References

- Spec: `docs/specs/2026-07-12-cbr-enhancements-design.md`
- Review: `~/adr/casehub-neocortex/cbr-enhancements-20260712-005521/`
- Blog: `blog/2026-07-12-mdp01-filling-in-the-cbr-gaps.md`
