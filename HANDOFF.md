# Handoff — 2026-07-10

## What Changed

Closed #89 (structured case fields). Three new `FeatureField` sealed variants — `CategoricalList`, `NestedObject`, `ObjectList` — with one-level nesting enforced via whitelist validation. `CbrFilter` sealed interface provides typed query predicates (`Contains`, `ContainsAll`, `ContainsAny`, `HasMatch`). `CbrQuery` gains separate `filters` field alongside scored `features`. `CbrFeatureValidator` consolidates validation across all backends. Qdrant backend maps filters to native `matchKeyword`/`matchKeywords`/`nested()` conditions with per-inner-field payload indexes. 67 contract tests (30 new). Design review: 5 rounds, 19 issues, 17 verified. Landed as `3ce41d5` on both `origin/main` and `upstream/main`.

Deferred issues filed: #125 (NumericList), #126 (NotContains filters), #127 (compound same-field filters), #128 (graded similarity for structured fields), #129 (ARC42 CBR module docs).

## Immediate Next Step

Pick next work item from What's Next. Track B head (#91 temporal representation) is now unblocked. Track C head (#84 outcome learning) is also unblocked.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low
- #129 — ARC42 CBR module documentation (§5 Building Block View) · M · Low

## What's Next — CBR App Enablement Critical Path

Track A complete. Track B unblocked by #89.

| # | Description | Scale | Complexity | Track | Notes |
|---|-------------|-------|------------|-------|-------|
| #91 | Temporal case representation (time-series segments) | M | High | B | Unblocked — structured fields (#89) landed |
| #92 | Sequence similarity (DTW, edit distance) | M | High | B | Blocked by #91 |
| #84 | Outcome learning + retrieval traceability | L | High | C | Unblocked — track C head |
| #85 | Plan adaptation SPI | M | High | C | Blocked by #84 |

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #120 | Expansion drift metrics with auto-fallback | M | Med | |
| #125 | NumericList field type | S | Low | Deferred from #89 |
| #126 | NotContains / NotContainsAny filters | S | Low | Deferred from #89 |
| #127 | Compound same-field filters (AllOf) | S | Low | Deferred from #89 |

## Key References

- Spec: `docs/specs/2026-07-10-structured-case-fields-design.md`
- Review: `~/adr/casehub-neocortex/structured-case-fields-20260710-031328/`
- Blog: `blog/2026-07-10-mdp01-when-flat-features-arent-enough.md`
