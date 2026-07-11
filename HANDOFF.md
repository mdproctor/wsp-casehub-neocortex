# Handoff — 2026-07-11

## What Changed

Closed #91 (temporal case representation) and delivered core #92 algorithms. Two new `FeatureField` sealed permits — `TimeSeries` (ordered multi-dimensional observations with timestamp field, DTW similarity) and `DiscreteSequence` (ordered categorical labels, edit distance similarity). Both participate in `CbrSimilarityScorer` weighted composite scoring alongside flat features. Constructor validates timestamp field existence, Numeric type, and ≥1 non-timestamp Numeric for DTW distance. Design review: 1 round, 10 issues accepted. Landed as `1f3bbf1` on both `origin/main` and `upstream/main`. Filed epic #131 (typed CBR feature values) with 5 child issues (#132–#136) to fix `Map<String, Object>` type safety system-wide.

## Immediate Next Step

Pick next work item from What's Next. Track B continues with #92 (sequence similarity refinements — alignment path, windowed DTW). Track C head (#84 outcome learning) is unblocked.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low
- #129 — ARC42 CBR module documentation (§5 Building Block View) · M · Low

## What's Next — CBR App Enablement Critical Path

Track A complete. Track B: #91 landed, #92 partially delivered (DTW + edit distance done, alignment path deferred).

| # | Description | Scale | Complexity | Track | Notes |
|---|-------------|-------|------------|-------|-------|
| #92 | Sequence similarity refinements — alignment path extraction, windowed DTW, weighted edit distance | M | Med | B | Core algorithms delivered in #91; remaining: alignment path, SimilaritySpec for temporal fields |
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

## Key References

- Spec: `docs/specs/2026-07-10-temporal-case-representation-design.md`
- Review: `~/adr/casehub-neocortex/temporal-case-representation-20260710-192419/`
- Blog: `blog/2026-07-11-mdp01-when-flat-features-arent-enough-again.md`
