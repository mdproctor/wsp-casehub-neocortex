# AdaptiveFilter Generic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #319 — AdaptiveFilter should accept generic scored items, not just RetrievedChunk
**Issue group:** #319

**Goal:** Make AdaptiveFilter work on any scored item type via `ToDoubleFunction<T>`, and add CE-aware gap detection with boundary cutoff and cluster extension.

**Architecture:** New `AdaptiveFilterOptions<T>` record bundles config + score extractor + optional CE behaviour. `AdaptiveFilter.filter()` becomes generic. `AdaptiveSearchWrapper` updates its call site. All changes in rag-api + one call site in rag-scoring.

**Tech Stack:** Java 21, JUnit 5, AssertJ

## Global Constraints

- All new types in `rag-api` (pure Java, zero deps beyond `java.util.function`)
- No convenience overload — single generic method only
- Backward-compatible behaviour when CE options are not set

---

## Batch 1: Generic AdaptiveFilter with CE-aware options

### Task 1: AdaptiveFilterOptions<T> record + generic AdaptiveFilter + tests

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/AdaptiveFilterOptions.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/AdaptiveFilter.java`
- Modify: `rag-api/src/test/java/io/casehub/neocortex/rag/AdaptiveFilterTest.java`

**Interfaces:**
- Consumes: `AdaptiveSearchConfig` (unchanged)
- Produces: `AdaptiveFilterOptions<T>` (used by Task 2's `AdaptiveSearchWrapper` update), `AdaptiveFilter.filter(List<T>, int, AdaptiveFilterOptions<T>)`

- [ ] **Step 1: Create AdaptiveFilterOptions record**

```java
package io.casehub.neocortex.rag;

import java.util.Objects;
import java.util.function.Predicate;
import java.util.function.ToDoubleFunction;

public record AdaptiveFilterOptions<T>(
    AdaptiveSearchConfig config,
    ToDoubleFunction<T> scoreExtractor,
    Predicate<T> ceBoundary,
    double clusterGapThreshold
) {
    public AdaptiveFilterOptions {
        Objects.requireNonNull(config, "config must not be null");
        Objects.requireNonNull(scoreExtractor, "scoreExtractor must not be null");
        if (clusterGapThreshold < 0 || clusterGapThreshold > 1)
            throw new IllegalArgumentException("clusterGapThreshold must be in [0,1]");
    }

    public static <T> AdaptiveFilterOptions<T> of(AdaptiveSearchConfig config,
                                                    ToDoubleFunction<T> scoreExtractor) {
        return new AdaptiveFilterOptions<>(config, scoreExtractor, null, 0.0);
    }

    public AdaptiveFilterOptions<T> withCeBoundary(Predicate<T> ceBoundary) {
        return new AdaptiveFilterOptions<>(config, scoreExtractor, ceBoundary, clusterGapThreshold);
    }

    public AdaptiveFilterOptions<T> withClusterExtension(double clusterGapThreshold) {
        return new AdaptiveFilterOptions<>(config, scoreExtractor, ceBoundary, clusterGapThreshold);
    }
}
```

- [ ] **Step 2: Rewrite AdaptiveFilter.filter() to generic**

Replace the entire `AdaptiveFilter` class:

```java
package io.casehub.neocortex.rag;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class AdaptiveFilter {
    private AdaptiveFilter() {}

    public static <T> List<T> filter(List<T> scored, int requestedLimit,
                                      AdaptiveFilterOptions<T> options) {
        if (scored.isEmpty()) return List.of();

        var config = options.config();
        var extractor = options.scoreExtractor();

        var sorted = scored.stream()
            .sorted(Comparator.comparingDouble(extractor).reversed())
            .toList();

        var floored = new ArrayList<>(sorted.stream()
            .filter(item -> extractor.applyAsDouble(item) >= config.scoreFloor())
            .toList());

        // CE boundary cutoff
        if (options.ceBoundary() != null) {
            for (int i = 1; i < floored.size(); i++) {
                if (options.ceBoundary().test(floored.get(i - 1))
                        && !options.ceBoundary().test(floored.get(i))) {
                    floored.subList(i, floored.size()).clear();
                    break;
                }
            }
        }

        // Gap trim
        for (int i = 1; i < floored.size(); i++) {
            double gap = extractor.applyAsDouble(floored.get(i - 1))
                       - extractor.applyAsDouble(floored.get(i));
            if (gap >= config.gapThreshold()) {
                floored.subList(i, floored.size()).clear();
                break;
            }
        }

        // Min results guarantee
        if (floored.size() < config.minResults() && sorted.size() >= config.minResults()) {
            return sorted.subList(0, Math.min(config.minResults(), sorted.size()));
        }
        if (floored.size() < config.minResults()) {
            return sorted;
        }

        // Cluster extension
        if (options.clusterGapThreshold() > 0 && floored.size() > requestedLimit) {
            int end = requestedLimit;
            while (end < floored.size()) {
                double gap = extractor.applyAsDouble(floored.get(end - 1))
                           - extractor.applyAsDouble(floored.get(end));
                if (gap >= options.clusterGapThreshold()) break;
                end++;
            }
            return floored.subList(0, end);
        }

        return floored.size() > requestedLimit
            ? floored.subList(0, requestedLimit)
            : floored;
    }
}
```

- [ ] **Step 3: Rewrite existing tests against generic API**

Update all 7 existing tests to use `AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore)`. Same assertions — verifies backward compatibility.

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class AdaptiveFilterTest {

    private static RetrievedChunk chunk(String id, double score) {
        return new RetrievedChunk("content", id, score, Map.of());
    }

    private static final AdaptiveSearchConfig CONFIG = new AdaptiveSearchConfig(0.3, 0.2, 2, 2.0);
    private static final AdaptiveFilterOptions<RetrievedChunk> OPTIONS =
        AdaptiveFilterOptions.of(CONFIG, RetrievedChunk::relevanceScore);

    @Test
    void emptyInput_returnsEmpty() {
        var result = AdaptiveFilter.filter(List.of(), 10, OPTIONS);
        assertThat(result).isEmpty();
    }

    @Test
    void floor_removesLowScores() {
        var chunks = List.of(chunk("a", 0.9), chunk("b", 0.5), chunk("c", 0.1));
        var result = AdaptiveFilter.filter(chunks, 10, OPTIONS);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b");
    }

    @Test
    void gapTrim_removesAfterLargeGap() {
        var chunks = List.of(chunk("a", 0.9), chunk("b", 0.85), chunk("c", 0.5), chunk("d", 0.45));
        var result = AdaptiveFilter.filter(chunks, 10, OPTIONS);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b");
    }

    @Test
    void minResults_guaranteesMinimum() {
        var config = new AdaptiveSearchConfig(0.8, 0.2, 3, 2.0);
        var opts = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore);
        var chunks = List.of(chunk("a", 0.9), chunk("b", 0.5), chunk("c", 0.4));
        var result = AdaptiveFilter.filter(chunks, 10, opts);
        assertThat(result).hasSize(3);
    }

    @Test
    void minResults_returnsAllWhenFewerThanMinExist() {
        var config = new AdaptiveSearchConfig(0.8, 0.2, 5, 2.0);
        var opts = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore);
        var chunks = List.of(chunk("a", 0.9), chunk("b", 0.5));
        var result = AdaptiveFilter.filter(chunks, 10, opts);
        assertThat(result).hasSize(2);
    }

    @Test
    void requestedLimit_capsResults() {
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore);
        var chunks = List.of(chunk("a", 0.9), chunk("b", 0.8), chunk("c", 0.7));
        var result = AdaptiveFilter.filter(chunks, 2, opts);
        assertThat(result).hasSize(2);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b");
    }

    @Test
    void sortsResultsByScoreDescending() {
        var chunks = List.of(chunk("c", 0.5), chunk("a", 0.9), chunk("b", 0.7));
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore);
        var result = AdaptiveFilter.filter(chunks, 10, opts);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b", "c");
    }

    @Test
    void floorAndGapInteract_gapTrimmedThenFloorApplied() {
        var chunks = List.of(chunk("a", 0.9), chunk("b", 0.85), chunk("c", 0.4), chunk("d", 0.35));
        var result = AdaptiveFilter.filter(chunks, 10, OPTIONS);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b");
    }

    // --- CE boundary tests ---

    @Test
    void ceBoundary_truncatesAtCeToNonCeBoundary() {
        record Item(String id, double score, boolean hasCe) {}
        var items = List.of(
            new Item("a", 0.9, true), new Item("b", 0.8, true),
            new Item("c", 0.7, false), new Item("d", 0.6, false));
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, Item::score)
            .withCeBoundary(Item::hasCe);
        var result = AdaptiveFilter.filter(items, 10, opts);
        assertThat(result).extracting(Item::id).containsExactly("a", "b");
    }

    @Test
    void ceBoundary_allCeItemsPassThrough() {
        record Item(String id, double score, boolean hasCe) {}
        var items = List.of(
            new Item("a", 0.9, true), new Item("b", 0.8, true));
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, Item::score)
            .withCeBoundary(Item::hasCe);
        var result = AdaptiveFilter.filter(items, 10, opts);
        assertThat(result).extracting(Item::id).containsExactly("a", "b");
    }

    @Test
    void ceBoundary_noCeItemsPassThrough() {
        record Item(String id, double score, boolean hasCe) {}
        var items = List.of(
            new Item("a", 0.9, false), new Item("b", 0.8, false));
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, Item::score)
            .withCeBoundary(Item::hasCe);
        var result = AdaptiveFilter.filter(items, 10, opts);
        assertThat(result).extracting(Item::id).containsExactly("a", "b");
    }

    // --- Cluster extension tests ---

    @Test
    void clusterExtension_extendsIntoDenseCluster() {
        var chunks = List.of(
            chunk("a", 0.9), chunk("b", 0.88), chunk("c", 0.86),
            chunk("d", 0.84), chunk("e", 0.5));
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore)
            .withClusterExtension(0.05);
        var result = AdaptiveFilter.filter(chunks, 2, opts);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b", "c", "d");
    }

    @Test
    void clusterExtension_stopsAtGap() {
        var chunks = List.of(
            chunk("a", 0.9), chunk("b", 0.88), chunk("c", 0.7));
        var config = new AdaptiveSearchConfig(0.0, 1.0, 0, 1.0);
        var opts = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore)
            .withClusterExtension(0.05);
        var result = AdaptiveFilter.filter(chunks, 2, opts);
        assertThat(result).extracting(RetrievedChunk::sourceDocumentId)
            .containsExactly("a", "b");
    }

    // --- Generic type test ---

    @Test
    void genericType_worksWithNonChunkType() {
        record SearchResult(String id, double score) {}
        var items = List.of(
            new SearchResult("x", 0.9), new SearchResult("y", 0.5),
            new SearchResult("z", 0.1));
        var config = new AdaptiveSearchConfig(0.3, 0.2, 2, 2.0);
        var opts = AdaptiveFilterOptions.of(config, SearchResult::score);
        var result = AdaptiveFilter.filter(items, 10, opts);
        assertThat(result).extracting(SearchResult::id)
            .containsExactly("x", "y");
    }
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=AdaptiveFilterTest`
Expected: all 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git -C <PROJECT> add rag-api/src/main/java/io/casehub/neocortex/rag/AdaptiveFilterOptions.java rag-api/src/main/java/io/casehub/neocortex/rag/AdaptiveFilter.java rag-api/src/test/java/io/casehub/neocortex/rag/AdaptiveFilterTest.java
git -C <PROJECT> commit -m "feat(rag-api): generic AdaptiveFilter with CE-aware options

Refs #319"
```

### Task 2: Update AdaptiveSearchWrapper call site

**Files:**
- Modify: `rag-scoring/src/main/java/io/casehub/neocortex/rag/scoring/AdaptiveSearchWrapper.java`

**Interfaces:**
- Consumes: `AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore)` from Task 1
- Produces: no API change — same public `search()` method

- [ ] **Step 1: Update AdaptiveSearchWrapper.search()**

Change the `AdaptiveFilter.filter()` call to use the generic API:

```java
// Line 43 — replace:
return AdaptiveFilter.filter(scored, maxResults, config);
// with:
var options = AdaptiveFilterOptions.of(config, RetrievedChunk::relevanceScore);
return AdaptiveFilter.filter(scored, maxResults, options);
```

Add import: `import io.casehub.neocortex.rag.AdaptiveFilterOptions;`

- [ ] **Step 2: Run AdaptiveSearchWrapper tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-scoring -Dtest=AdaptiveSearchWrapperTest`
Expected: all 6 tests PASS

- [ ] **Step 3: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git -C <PROJECT> add rag-scoring/src/main/java/io/casehub/neocortex/rag/scoring/AdaptiveSearchWrapper.java
git -C <PROJECT> commit -m "refactor(rag-scoring): update AdaptiveSearchWrapper for generic AdaptiveFilter

Closes #319"
```

---

## References

- [2026-09-11-adaptive-filter-generic-design.md] — design spec
- `rag-api/src/main/java/.../rag/AdaptiveFilter.java` — current implementation
- `rag-api/src/main/java/.../rag/AdaptiveSearchConfig.java` — config record
- `rag-scoring/src/main/java/.../scoring/AdaptiveSearchWrapper.java` — only in-repo consumer
- `rag-api/src/test/java/.../rag/AdaptiveFilterTest.java` — existing tests
- `rag-scoring/src/test/java/.../scoring/AdaptiveSearchWrapperTest.java` — wrapper tests
- [GitHub #319] — focal issue
- [Hortora/engine#94] — downstream migration unblocked by this
