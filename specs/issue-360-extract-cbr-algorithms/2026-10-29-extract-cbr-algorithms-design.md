# Extract cbr-algorithms from memory-api

**Issue:** casehubio/neocortex#360
**Parent:** casehubio/neocortex#355
**Date:** 2026-10-29

## Problem

memory-api is 229 Java files. The `cbr` sub-package contains 111 production files mixing SPI interfaces and value types with substantial pure-Java algorithm implementations. The algorithms are legitimate shared code used by multiple store backends, but they are not API surface.

## Solution

Extract a new `cbr-algorithms` module containing the algorithm implementations and their output-only value types. memory-api retains SPI interfaces, schema types, and value types referenced by SPIs.

### Dependency structure

```
memory-api  (SPI + value types, ~70 cbr files after extraction)
     ↑
cbr-algorithms  (scoring, DTW, edit distance, trend, validation, ~17 production files + ~12 test files)
     ↑
memory-cbr-inmem, memory-cbr-jpa, memory-cbr-spring-jpa, memory-qdrant, memory-core, cognition
```

Both modules are Tier 1 pure Java, zero CDI. `cbr-algorithms` depends on `memory-api` for input types. No reverse dependency.

### Files that move to cbr-algorithms

**Algorithm implementations:**

| File | Purpose |
|------|---------|
| `CbrSimilarityScorer` | Weighted composite scoring with type-specific similarity |
| `DtwSimilarity` | O(n×m) dynamic time warping |
| `LbKeogh` | O(n) Sakoe-Chiba envelope lower-bound pruning |
| `EditDistanceSimilarity` | Levenshtein with weighted substitution costs |
| `TrendAnalyzer` | Trend metrics: slope, delta, volatility, acceleration, change-points |
| `CbrRecordValidator` | Store-time, query-time, and filter validation |
| `CbrRecordFilterMatcher` | In-memory filter matching against feature records |

**Output-only value types** (only referenced by their algorithm, not by any SPI):

| File | Companion to |
|------|-------------|
| `DtwResult` | DtwSimilarity |
| `AlignmentPair` | DtwSimilarity |
| `EditDistanceResult` | EditDistanceSimilarity |
| `EditOp` | EditDistanceSimilarity |
| `EditStep` | EditDistanceSimilarity |
| `TrendProfile` | TrendAnalyzer |
| `TrendFieldNaming` | TrendAnalyzer |

**Tests that move** (all in `memory-api/src/test/.../cbr/`):

| File | Tests |
|------|-------|
| `CbrSimilarityScorerTest` | CbrSimilarityScorer |
| `DtwSimilarityTest` | DtwSimilarity |
| `LbKeoghTest` | LbKeogh |
| `EditDistanceSimilarityTest` | EditDistanceSimilarity |
| `TrendAnalyzerTest` | TrendAnalyzer |
| `TrendFieldNamingTest` | TrendFieldNaming |
| `CbrFeatureValidatorTest` | CbrRecordValidator |
| `CbrRecordFilterMatcherTest` | CbrRecordFilterMatcher |
| `WarpingConstraintTest` | WarpingConstraint (stays but tests DTW integration) |

### Files that stay in memory-api

**Schema/config types referenced by SPIs:**
- `WarpingConstraint` — referenced by `SimilaritySpec.DtwSpec`
- `TrendSpec`, `TrendType` — referenced by `FeatureField.TimeSeries`
- `SimilaritySpec` — schema definition sealed hierarchy
- `NumericRange` — referenced by `FeatureField`
- `FeatureStatistics` — referenced by `CbrSuggestions`
- `LocalSimilarityFunction` — SPI functional interface

**All SPI interfaces, store contracts, value types, events, traces** — unchanged.

### Maven coordinates

| Element | Value |
|---------|-------|
| artifactId | `casehub-neocortex-cbr-algorithms` |
| groupId | `io.casehub` |
| Java package | `io.casehub.neocortex.memory.cbr` (unchanged — same package, different module) |

Same package across both modules avoids import changes in all consumers. Package-private access is not used by the algorithm classes (all public static utility methods), so split-package works cleanly here.

### Consumer dependency changes

Every module that imports an algorithm class adds `cbr-algorithms` to its POM:

| Module | Uses |
|--------|------|
| `memory-cbr-inmem` | CbrSimilarityScorer, CbrRecordValidator, LbKeogh |
| `memory-cbr-jpa` | CbrSimilarityScorer, CbrRecordValidator, CbrRecordFilterMatcher |
| `memory-cbr-spring-jpa` | CbrSimilarityScorer, CbrRecordValidator, CbrRecordFilterMatcher |
| `memory-qdrant` | CbrSimilarityScorer, CbrRecordValidator |
| `memory-core` | CbrSimilarityScorer (DiversityCbrRecordStore), TrendAnalyzer (TrendEnrichmentCbrRecordStore) |
| `memory-testing` | CbrSimilarityScorer (contract tests) |
| `cognition` | TrendAnalyzer (StrategyLearningOrchestrator) |

### WarpingConstraintTest placement

`WarpingConstraintTest` tests the `WarpingConstraint` sealed hierarchy which stays in memory-api. It should stay in memory-api — it tests the value type, not the DTW algorithm.

## Scope

- New `cbr-algorithms` module: pom.xml, move files, move tests
- Update consumer POMs to add `cbr-algorithms` dependency
- Update parent pom.xml module list
- Update CLAUDE.md module structure and Maven coordinates
- No import changes needed (same package)
- No code changes needed (pure file moves + POM wiring)

## References

- casehubio/neocortex#360 — this issue
- casehubio/neocortex#355 — parent: memory-api reduction
- `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/` — source package
- `ide_find_references` analysis — confirmed no SPI→algorithm references
