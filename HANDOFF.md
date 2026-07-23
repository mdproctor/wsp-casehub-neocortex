# Handoff — 2026-07-23

## What Changed

Branch `issue-171-batch-s-xs-fixes` closed. Landed as `d6de6ae` on main. Pushed to both origin and upstream. Closes #171, #172, #170, #157, #145, #146. Issues #164 and #116 closed earlier (already implemented / confirmed). Issue #62 rescaled to M/Med with design gap documented.

**Delivered:** Batch of S/XS fixes across memory-api, memory, memory-cbr-tracking, rag-expansion, and specs. Key items: FeatureStatistics + CbrSuggestions records in memory-api (unblocks casehub-life migration), CDI decorator chain @QuarkusTest, double-recording guard bug fix (delegate instanceof → Instance.isResolvable()), SmallRye Config mapping fix (enabled() on CbrTrackingConfig/OutcomeWeightingConfig), spec corrections for @ObservesAsync and AdaptedStep nullability.

## Immediate Next Step

Pick next from backlog. No blockers.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #62 | ColBertRelevanceEvaluator — CRAG compatibility | M | Med | Needs per-leg score propagation first |
| #168 | Engine gardenUnretrieved → use RetrievalAnalyzer | S | Low | Cross-repo (engine) |
| #167 | Query→document→outcome correlation graph | M | High | Follow-up from #109 |
| #166 | Reactive JPA backend for CbrCaseMemoryStore | M | Med | Eliminate blocking bridge |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |

## Key Findings

- **Bridge detection bug (#146):** `delegate instanceof BridgedCbrStore` fails with intermediate CDI decorators. Fixed with `Instance<BridgedCbrStore>.isResolvable()`.
- **SmallRye Config (#145):** `@IfBuildProperty` keys under a `@ConfigMapping` prefix must be declared in the mapping interface (Quarkus 3.32+).
- **#62 design gap:** RelevanceEvaluator takes raw strings, not RetrievedChunk. Per-leg scores lost in fusion.

## Garden Entries

- GE-20260723-e19b4a: CDI decorator delegate instanceof check fails with intermediate decorators
- GE-20260723-64e384: SmallRye Config rejects @IfBuildProperty keys not in @ConfigMapping

## References

- Stale workspace branches: issue-110 (10d), issue-46 (21d), issue-56 (10d)
