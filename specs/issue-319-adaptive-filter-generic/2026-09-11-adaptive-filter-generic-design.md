# AdaptiveFilter Generic Scored Items

**Date:** 2026-09-11
**Issue:** #319
**Status:** Draft

---

## 1. Problem

`AdaptiveFilter.filter()` is hardcoded to `RetrievedChunk`. Consumers that apply adaptive filtering after mapping to domain-specific result types (e.g., engine's `SearchResult`) or after federation merge can't use it without mapping back to `RetrievedChunk`.

Engine's `SearchResource.adaptiveFilter()` (~90 lines) reimplements the same floor + gap trimming logic on `SearchResult`, plus CE-aware gap detection that upstream lacks.

---

## 2. Design

### 2.1 Generic Filter Method

Replace the current method signature:

```java
// Before
public static List<RetrievedChunk> filter(List<RetrievedChunk> scored,
                                           int requestedLimit,
                                           AdaptiveSearchConfig config)

// After
public static <T> List<T> filter(List<T> scored,
                                  int requestedLimit,
                                  AdaptiveFilterOptions<T> options)
```

No convenience overload. The single generic method handles all cases.

### 2.2 AdaptiveFilterOptions<T>

New record in `rag-api`:

```java
public record AdaptiveFilterOptions<T>(
    AdaptiveSearchConfig config,
    ToDoubleFunction<T> scoreExtractor,
    Predicate<T> ceBoundary,
    double clusterGapThreshold
) {
    // ...
}
```

**Fields:**

| Field | Type | Required | Default | Purpose |
|-------|------|----------|---------|---------|
| `config` | `AdaptiveSearchConfig` | yes | — | Score floor, gap threshold, min results, overfetch multiplier |
| `scoreExtractor` | `ToDoubleFunction<T>` | yes | — | Extracts the primary score from any item type |
| `ceBoundary` | `Predicate<T>` | no | `null` | When non-null, a CE-scored item followed by a non-CE item triggers a hard cutoff |
| `clusterGapThreshold` | `double` | no | `0.0` | When > 0, extends results beyond `requestedLimit` into dense clusters where consecutive gap < this value |

**Factory methods:**

```java
// Basic — no CE awareness
public static <T> AdaptiveFilterOptions<T> of(AdaptiveSearchConfig config,
                                               ToDoubleFunction<T> scoreExtractor)

// With CE boundary
public AdaptiveFilterOptions<T> withCeBoundary(Predicate<T> ceBoundary)

// With cluster extension
public AdaptiveFilterOptions<T> withClusterExtension(double clusterGapThreshold)
```

`withCeBoundary` and `withClusterExtension` return new instances (immutable record).

### 2.3 Filter Algorithm — Extended

The algorithm extends the current three-stage pipeline with two optional CE-aware stages:

1. **Sort** by score descending (via `scoreExtractor`)
2. **Floor** — remove items with score < `config.scoreFloor()`
3. **CE boundary cutoff** (when `ceBoundary != null`) — scan sorted items; when `ceBoundary.test(item)` is true for item `i-1` and false for item `i`, truncate at position `i`. This catches the qualitative boundary between cross-encoder-validated results and unvalidated ones
4. **Gap trim** — same as current: truncate when consecutive score gap ≥ `config.gapThreshold()`
5. **Min results guarantee** — same as current
6. **Cluster extension** (when `clusterGapThreshold > 0`) — after applying `requestedLimit`, continue including items while consecutive gap < `clusterGapThreshold`. This prevents cutting inside a tight score cluster
7. **Requested limit** — cap to `requestedLimit` (only when cluster extension is inactive)

Steps 3 and 6 are no-ops when their corresponding options are not set. The current behaviour is preserved exactly when `AdaptiveFilterOptions.of(config, extractor)` is used without CE options.

### 2.4 AdaptiveSearchWrapper Update

`AdaptiveSearchWrapper` updates its call site:

```java
// Before
return AdaptiveFilter.filter(scored, maxResults, config);

// After
var options = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore);
return AdaptiveFilter.filter(scored, maxResults, options);
```

No change to `AdaptiveSearchWrapper`'s public API.

### 2.5 Module Placement

All new types stay in `rag-api`:

| Type | Module | Dependencies |
|------|--------|-------------|
| `AdaptiveFilterOptions<T>` | rag-api | `java.util.function` only |
| `AdaptiveFilter` (updated) | rag-api | `AdaptiveFilterOptions`, `AdaptiveSearchConfig` |
| `AdaptiveSearchConfig` | rag-api | unchanged |

No new module dependencies. Engine consumers get generic filtering via their existing `rag-api` dependency.

---

## 3. What's NOT Covered

- Engine-side migration (`SearchResource.adaptiveFilter()` deletion) — that's Hortora/engine#94
- Score normalization between CE and non-CE results — consumers handle this
- Integration with CRAG decorator chain — CRAG operates upstream of AdaptiveFilter

---

## 4. Testing

- All existing `AdaptiveFilterTest` tests rewritten against the generic API (same assertions, `RetrievedChunk::relevanceScore` as extractor)
- New tests for CE boundary cutoff (mixed CE/non-CE items, boundary at various positions)
- New tests for cluster extension (tight cluster that would be split by requestedLimit)
- New test with a non-`RetrievedChunk` type (plain record with a score field) to verify generics work end-to-end
- `AdaptiveSearchWrapperTest` updated for new call site

---

## 5. Estimated Size

~150 lines of production code (new `AdaptiveFilterOptions` + updated `AdaptiveFilter`), ~100 lines of new tests. Small change, contained in `rag-api` + one call site in `rag-scoring`.

---

## References

- `rag-api/src/main/java/.../rag/AdaptiveFilter.java` — current implementation (42 lines)
- `rag-api/src/main/java/.../rag/AdaptiveSearchConfig.java` — config record
- `rag-scoring/src/main/java/.../scoring/AdaptiveSearchWrapper.java` — only in-repo consumer
- `rag-api/src/test/java/.../rag/AdaptiveFilterTest.java` — existing tests (7 tests)
- Hortora/engine `SearchResource.adaptiveFilter()` — CE-aware reimplementation this replaces
- Hortora/engine#94 — engine-side migration blocked on this
- casehubio/neocortex#319 — this issue
