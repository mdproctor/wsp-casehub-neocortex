# Handoff — 2026-07-20

## What Changed

Branch `issue-169-structured-field-defaults` closed. Landed as `876a1f7` on main. Pushed to both origin and upstream. Closes #169.

**Delivered:** Built-in type defaults for all four structured CBR field types in `CbrSimilarityScorer`:
- **CategoricalList** → Jaccard similarity on string sets
- **NumericList** → average nearest-neighbor with linear decay
- **NestedObject** → recursive scoring with uniform weights
- **ObjectList** → greedy best-match with recursive inner scoring

Also: `CbrFeatureValidator.validateQueryFeatures()` now accepts structured fields (was: "must be queried via filters"). Removed the `continue` guard and dead-code `return 0.0` branches. Design review: 3 rounds, 12 issues, all verified. Follow-up filed: #170 (validateFlatFields error messages).

Hygiene scan recovered 3 artifacts from closed branches to workspace main (2 specs, 1 blog).

## Immediate Next Step

Pick next from backlog. No blockers.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #170 | Update validateFlatFields error messages from "filter-only" | XS | Low | Follow-up from #169 |
| #168 | Engine gardenUnretrieved → use RetrievalAnalyzer | S | Low | Cross-repo (engine) |
| #167 | Query→document→outcome correlation graph | M | High | Follow-up from #109 |
| #166 | Reactive JPA backend for CbrCaseMemoryStore | M | Med | Eliminate blocking bridge |
| #157 | FeatureStatistics + CbrSuggestions → memory-api | M | Med | Currently in casehub-life |
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |

## References

- Spec: `docs/specs/2026-07-20-structured-field-similarity-defaults-design.md` (project)
- Plan: `plans/attic/issue-169-structured-field-defaults/2026-07-20-structured-field-similarity-defaults.md` (workspace)
- Design review: `~/adr/casehub-neocortex/structured-field-similarity-defaults-20260720-020735/` (3 rounds, 12 issues)
- Follow-up: #170 (validateFlatFields error messages)
