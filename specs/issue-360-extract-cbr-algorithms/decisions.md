## D1: Module name

**Choice:** `cbr-algorithms`
**Alternatives:**
- `cbr-core` — implies foundational/depended-on-by-everything, misleading since memory-api doesn't depend on it
**Rationale:** Accurately describes contents: scoring, DTW, edit distance, trend analysis, validation
**Trade-offs:** Slightly longer name
**Sources:** #360 issue description, memory-api codebase analysis
**Exploration:** quick
**Status:** captured

## D2: Split boundary

**Choice:** Algorithm implementations + their output-only value types move; SPI interfaces, schema types, and value types referenced by SPIs stay
**Alternatives:**
- Move all cbr/ types to cbr-algorithms — breaks SPI contract, memory-api would depend on cbr-algorithms
- Move only algorithm classes, leave all value types — creates import of output types (DtwResult, TrendProfile) from memory-api that have no SPI relationship
**Rationale:** Clean dependency: cbr-algorithms depends on memory-api for input types (FeatureValue, SimilaritySpec, CbrRecordSchema), memory-api has zero knowledge of cbr-algorithms. Output types (DtwResult, EditDistanceResult, TrendProfile, TrendFieldNaming) only meaningful alongside their algorithm.
**Trade-offs:** None significant — the types that stay (WarpingConstraint, TrendSpec, TrendType, FeatureStatistics, NumericRange) are genuinely schema/SPI surface
**Sources:** ide_find_references analysis showing no SPI→algorithm references
**Exploration:** quick
**Status:** captured
