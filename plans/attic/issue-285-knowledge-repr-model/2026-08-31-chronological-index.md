# Chronological Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #237 — Chronological index
**Issue group:** #253, #229, #232, #234, #235, #236, #237

**Goal:** Build a cross-store temporal aggregator that queries MindMap,
Memory, and CBR stores and merges results into a single chronological
timeline.

**Architecture:** New `cognitive-index` module with a stateless CDI bean
(`TemporalIndex`) that queries available stores via `Instance<T>` for
graceful degradation. Value types (`TemporalEntry`, `TemporalSource`,
`TemporalQuery`, `TemporalRanker`) are pure Java records/interfaces.
This is a derived view, not a store — no persistence, no SPI hierarchy.

**Tech Stack:** Java 21, Quarkus CDI (`@ApplicationScoped`, `Instance<T>`),
JUnit 5, AssertJ

## Global Constraints

- Java 21 source level (`maven.compiler.release=21`), Java 26 JVM
- Parent POM: `casehub-neocortex-parent` version `0.2-SNAPSHOT`
- All public classes must carry javadoc explaining "derived view, not a store"
- Use `ide-tooling` for all code navigation and structural editing
- Commit after every task
- `Refs #237` on every commit message

---

## Batch 1: Module scaffold + value types

### Task 1: Create cognitive-index module with pom.xml

**Files:**
- Create: `cognitive-index/pom.xml`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/.gitkeep`
- Modify: `pom.xml` (parent — add module + dependency management)

**Interfaces:**
- Consumes: nothing
- Produces: Maven module `casehub-neocortex-cognitive-index` with
  compile deps on `cognitive-api`, `mindmap-api`, `memory-api`;
  test deps on `junit-jupiter`, `assertj-core`, `mindmap-inmem`,
  `memory-inmem`

- [ ] **Step 1: Create `cognitive-index/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
    </parent>
    <artifactId>casehub-neocortex-cognitive-index</artifactId>
    <name>CaseHub Neocortex Cognitive Index</name>
    <description>Cross-store cognitive query utilities — temporal aggregation, entity resolution</description>
    <dependencies>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-cognitive-api</artifactId>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-mindmap-api</artifactId>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-api</artifactId>
        </dependency>
        <dependency>
            <groupId>jakarta.enterprise</groupId>
            <artifactId>jakarta.enterprise.cdi-api</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>jakarta.inject</groupId>
            <artifactId>jakarta.inject-api</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-mindmap-inmem</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-inmem</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2: Add module to parent pom.xml**

In the parent `pom.xml`, add `<module>cognitive-index</module>` after the
`cognitive-api` module in the `<modules>` section. Also add dependency
management entry:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-cognitive-index</artifactId>
    <version>${project.version}</version>
</dependency>
```

Add this after the `casehub-neocortex-cognitive-api` dependency management
entry (around line 195).

- [ ] **Step 3: Create source directory**

Create the package directory:
`cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/`
and `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/`

- [ ] **Step 4: Verify build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl cognitive-index -am`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```
git add cognitive-index/ pom.xml
git commit -m "feat(cognitive-index): scaffold module with pom.xml

Refs #237"
```

### Task 2: TemporalSource sealed interface + TemporalEntry record

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalSource.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalEntry.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/TemporalEntryTest.java`

**Interfaces:**
- Consumes: `MindMapNode` (mindmap-api), `Memory` (memory-api),
  `ScoredCbrCase` (memory-api), `Confidence` (cognitive-api)
- Produces: `TemporalSource` sealed interface with `FromMindMap`,
  `FromMemory`, `FromCbr` variants; `TemporalEntry` record with
  `Comparable<TemporalEntry>` (chronological ordering)

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TemporalEntryTest {

    private static final Instant T1 = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T2 = Instant.parse("2026-01-01T11:00:00Z");
    private static final Instant T3 = Instant.parse("2026-01-01T12:00:00Z");
    private static final Confidence CONF = new Confidence(ConfidenceOrigin.STATED, 0.9, T1);

    @Test
    void compareTo_sortsChronologically() {
        var early = new TemporalEntry(T1, new TemporalSource.FromMemory(null), "t1", CONF);
        var middle = new TemporalEntry(T2, new TemporalSource.FromMemory(null), "t1", CONF);
        var late = new TemporalEntry(T3, new TemporalSource.FromMemory(null), "t1", CONF);

        var sorted = List.of(late, early, middle).stream().sorted().toList();
        assertThat(sorted).containsExactly(early, middle, late);
    }

    @Test
    void nullTimestamp_throws() {
        assertThatThrownBy(() -> new TemporalEntry(null, new TemporalSource.FromMemory(null), "t1", CONF))
            .isInstanceOf(NullPointerException.class)
            .hasMessageContaining("timestamp");
    }

    @Test
    void nullSource_throws() {
        assertThatThrownBy(() -> new TemporalEntry(T1, null, "t1", CONF))
            .isInstanceOf(NullPointerException.class)
            .hasMessageContaining("source");
    }

    @Test
    void nullTenantId_throws() {
        assertThatThrownBy(() -> new TemporalEntry(T1, new TemporalSource.FromMemory(null), null, CONF))
            .isInstanceOf(NullPointerException.class)
            .hasMessageContaining("tenantId");
    }

    @Test
    void nullConfidence_allowed() {
        var entry = new TemporalEntry(T1, new TemporalSource.FromMemory(null), "t1", null);
        assertThat(entry.confidence()).isNull();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=TemporalEntryTest`
Expected: FAIL — classes don't exist

- [ ] **Step 3: Implement TemporalSource**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import io.casehub.neocortex.mindmap.MindMapNode;

/**
 * The originating store and full source object for a {@link TemporalEntry}.
 * Sealed — exhaustive switch coverage ensures new store variants are a
 * compile error at every consumer.
 *
 * <p>This is part of a derived view over existing store data. The source
 * objects are owned by their originating stores, not by this type.
 */
public sealed interface TemporalSource {
    record FromMindMap(MindMapNode node) implements TemporalSource {}
    record FromMemory(Memory memory) implements TemporalSource {}
    record FromCbr(ScoredCbrCase<?> cbrCase) implements TemporalSource {}
}
```

- [ ] **Step 4: Implement TemporalEntry**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;

import java.time.Instant;
import java.util.Objects;

/**
 * A single temporal event from any cognitive store. This is a derived view —
 * the source data lives in the originating store (MindMap, Memory, or CBR).
 * TemporalEntry carries the full source object via {@link TemporalSource}
 * for zero-information-loss access.
 *
 * <p>Natural ordering is chronological (oldest first). Confidence is nullable —
 * null means "no confidence assessment."
 */
public record TemporalEntry(
    Instant timestamp,
    TemporalSource source,
    String tenantId,
    Confidence confidence
) implements Comparable<TemporalEntry> {

    public TemporalEntry {
        Objects.requireNonNull(timestamp, "timestamp required");
        Objects.requireNonNull(source, "source required");
        Objects.requireNonNull(tenantId, "tenantId required");
    }

    @Override
    public int compareTo(TemporalEntry other) {
        return this.timestamp.compareTo(other.timestamp);
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=TemporalEntryTest`
Expected: PASS — all 5 tests green

- [ ] **Step 6: Commit**

```
git add cognitive-index/src/
git commit -m "feat(cognitive-index): TemporalEntry + TemporalSource value types

Refs #237"
```

### Task 3: TemporalQuery record + TemporalRanker interface

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalQuery.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalRanker.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/TemporalQueryTest.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/TemporalRankerTest.java`

**Interfaces:**
- Consumes: nothing (pure value types)
- Produces: `TemporalQuery` record with `StoreKind` enum, factory methods
  `since()`, `window()`, `upcoming()`, `withSources()`, `withEntityIds()`;
  `TemporalRanker` functional interface with `score()`, `rank()`, `recency()`

**Design note — entityIds on TemporalQuery:**
`MemoryQuery` requires non-empty `entityIds`. TemporalIndex needs entity
context (typically agentId) to query the memory store. `TemporalQuery`
carries an optional `Collection<String> entityIds`. When empty, the
Memory store is silently skipped even if `MEMORY` is in `sources`.

- [ ] **Step 1: Write failing tests for TemporalQuery**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TemporalQueryTest {

    private static final Instant NOW = Instant.parse("2026-01-01T12:00:00Z");
    private static final Instant HOUR_AGO = NOW.minusSeconds(3600);

    @Test
    void since_createsQueryWithFromAndAllSources() {
        var query = TemporalQuery.since(List.of("t1"), HOUR_AGO, 50);
        assertThat(query.from()).isEqualTo(HOUR_AGO);
        assertThat(query.to()).isNull();
        assertThat(query.limit()).isEqualTo(50);
        assertThat(query.sources()).isEqualTo(EnumSet.allOf(TemporalQuery.StoreKind.class));
        assertThat(query.entityIds()).isEmpty();
    }

    @Test
    void window_setsFromAndTo() {
        var query = TemporalQuery.window(List.of("t1"), HOUR_AGO, NOW, 20);
        assertThat(query.from()).isEqualTo(HOUR_AGO);
        assertThat(query.to()).isEqualTo(NOW);
    }

    @Test
    void upcoming_queriesOnlyMindMap() {
        var query = TemporalQuery.upcoming(List.of("t1"), NOW, 10);
        assertThat(query.sources()).isEqualTo(EnumSet.of(TemporalQuery.StoreKind.MINDMAP));
        assertThat(query.from()).isEqualTo(NOW);
    }

    @Test
    void emptyTenantIds_throws() {
        assertThatThrownBy(() -> TemporalQuery.since(List.of(), HOUR_AGO, 10))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("tenantId");
    }

    @Test
    void nonPositiveLimit_throws() {
        assertThatThrownBy(() -> TemporalQuery.since(List.of("t1"), HOUR_AGO, 0))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("limit");
    }

    @Test
    void nullSources_defaultsToAll() {
        var query = new TemporalQuery(List.of("t1"), HOUR_AGO, null, 10, null, List.of());
        assertThat(query.sources()).isEqualTo(EnumSet.allOf(TemporalQuery.StoreKind.class));
    }

    @Test
    void withSources_replacesSourceSet() {
        var query = TemporalQuery.since(List.of("t1"), HOUR_AGO, 10)
            .withSources(Set.of(TemporalQuery.StoreKind.CBR));
        assertThat(query.sources()).containsExactly(TemporalQuery.StoreKind.CBR);
    }

    @Test
    void withEntityIds_setsEntityIds() {
        var query = TemporalQuery.since(List.of("t1"), HOUR_AGO, 10)
            .withEntityIds(List.of("agent-1"));
        assertThat(query.entityIds()).containsExactly("agent-1");
    }
}
```

- [ ] **Step 2: Write failing tests for TemporalRanker**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class TemporalRankerTest {

    private static final Instant NOW = Instant.parse("2026-01-01T12:00:00Z");
    private static final Confidence CONF = new Confidence(ConfidenceOrigin.STATED, 0.9, NOW);

    @Test
    void recency_newerScoresHigher() {
        var ranker = TemporalRanker.recency();
        var recent = new TemporalEntry(NOW.minusSeconds(60), new TemporalSource.FromMemory(null), "t1", CONF);
        var old = new TemporalEntry(NOW.minusSeconds(3600), new TemporalSource.FromMemory(null), "t1", CONF);

        assertThat(ranker.score(recent, NOW)).isGreaterThan(ranker.score(old, NOW));
    }

    @Test
    void recency_approachingFutureScoresHigher() {
        var ranker = TemporalRanker.recency();
        var soon = new TemporalEntry(NOW.plusSeconds(60), new TemporalSource.FromMemory(null), "t1", CONF);
        var far = new TemporalEntry(NOW.plusSeconds(3600), new TemporalSource.FromMemory(null), "t1", CONF);

        assertThat(ranker.score(soon, NOW)).isGreaterThan(ranker.score(far, NOW));
    }

    @Test
    void rank_reordersByScoreDescending() {
        var ranker = TemporalRanker.recency();
        var old = new TemporalEntry(NOW.minusSeconds(3600), new TemporalSource.FromMemory(null), "t1", CONF);
        var recent = new TemporalEntry(NOW.minusSeconds(60), new TemporalSource.FromMemory(null), "t1", CONF);

        var ranked = ranker.rank(List.of(old, recent), NOW);
        assertThat(ranked).containsExactly(recent, old);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest="TemporalQueryTest,TemporalRankerTest"`
Expected: FAIL — classes don't exist

- [ ] **Step 4: Implement TemporalQuery**

```java
package io.casehub.neocortex.cognitive.index;

import java.time.Instant;
import java.util.Collection;
import java.util.EnumSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * Specifies what to query from the {@link TemporalIndex} — time range,
 * tenants, and which stores to include. Factory methods cover common
 * patterns: {@link #since}, {@link #window}, {@link #upcoming}.
 *
 * <p>{@code entityIds} provides entity context for the Memory store
 * (required by {@link io.casehub.neocortex.memory.MemoryQuery}).
 * When empty, the Memory store is silently skipped even if
 * {@link StoreKind#MEMORY} is in {@code sources}.
 */
public record TemporalQuery(
    Collection<String> tenantIds,
    Instant from,
    Instant to,
    int limit,
    Set<StoreKind> sources,
    Collection<String> entityIds
) {
    public enum StoreKind { MINDMAP, MEMORY, CBR }

    public TemporalQuery {
        Objects.requireNonNull(tenantIds, "tenantIds required");
        if (tenantIds.isEmpty()) throw new IllegalArgumentException("at least one tenantId required");
        if (limit <= 0) throw new IllegalArgumentException("limit must be positive");
        if (sources == null || sources.isEmpty()) {
            sources = EnumSet.allOf(StoreKind.class);
        }
        if (entityIds == null) {
            entityIds = List.of();
        }
        tenantIds = List.copyOf(tenantIds);
        entityIds = List.copyOf(entityIds);
    }

    public static TemporalQuery since(Collection<String> tenantIds, Instant from, int limit) {
        return new TemporalQuery(tenantIds, from, null, limit, EnumSet.allOf(StoreKind.class), List.of());
    }

    public static TemporalQuery window(Collection<String> tenantIds, Instant from, Instant to, int limit) {
        return new TemporalQuery(tenantIds, from, to, limit, EnumSet.allOf(StoreKind.class), List.of());
    }

    public static TemporalQuery upcoming(Collection<String> tenantIds, Instant now, int limit) {
        return new TemporalQuery(tenantIds, now, null, limit, EnumSet.of(StoreKind.MINDMAP), List.of());
    }

    public TemporalQuery withSources(Set<StoreKind> sources) {
        return new TemporalQuery(tenantIds, from, to, limit, sources, entityIds);
    }

    public TemporalQuery withEntityIds(Collection<String> entityIds) {
        return new TemporalQuery(tenantIds, from, to, limit, sources, entityIds);
    }
}
```

- [ ] **Step 5: Implement TemporalRanker**

```java
package io.casehub.neocortex.cognitive.index;

import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;

/**
 * Composable scoring function for re-ordering {@link TemporalEntry} results.
 * Orthogonal to {@link TemporalIndex} — the index produces chronological
 * data, the ranker re-orders it by salience or any other criterion.
 *
 * <p>This is not a store or a persistent component. It is a pure function
 * over derived view data from {@link TemporalIndex}.
 */
@FunctionalInterface
public interface TemporalRanker {

    double score(TemporalEntry entry, Instant now);

    default List<TemporalEntry> rank(List<TemporalEntry> entries, Instant now) {
        return entries.stream()
            .sorted(Comparator.comparingDouble((TemporalEntry e) -> score(e, now)).reversed())
            .toList();
    }

    static TemporalRanker recency() {
        return (entry, now) -> {
            long seconds = Duration.between(entry.timestamp(), now).abs().getSeconds();
            return 1.0 / (1.0 + seconds);
        };
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest="TemporalQueryTest,TemporalRankerTest"`
Expected: PASS — all 11 tests green

- [ ] **Step 7: Commit**

```
git add cognitive-index/src/
git commit -m "feat(cognitive-index): TemporalQuery + TemporalRanker

Refs #237"
```

## Batch 2: TemporalIndex CDI bean + integration tests

### Task 4: TemporalIndex implementation

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalIndex.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/TemporalIndexTest.java`

**Interfaces:**
- Consumes: `MindMapStore.search(MindMapQuery)` (mindmap-api),
  `CaseMemoryStore.query(MemoryQuery)` (memory-api),
  `CaseMemoryStore.scan(MemoryScanRequest)` (memory-api),
  `TemporalQuery`, `TemporalEntry`, `TemporalSource`
- Produces: `TemporalIndex` CDI bean with `List<TemporalEntry> query(TemporalQuery)`

**Design notes:**
- Constructor injection with `Instance<T>` for all three stores
- MindMap timestamp heuristic: if `query.from()` is at or after
  `Instant.now()` (±1s tolerance), use `validAfter`; otherwise use
  `updatedAfter`
- Memory store: uses `MemoryQuery` with `entityIds` from the
  `TemporalQuery`. Silently skipped when `entityIds` is empty.
  Queries `experience` domain. Post-filters by `to` bound.
- CBR store: uses `scan()` — `CbrScanRequest` doesn't have temporal
  filtering, so post-filter `storedAt` by `from`/`to`. Requires
  domain and caseType — for now, skip CBR (it needs more query
  context than TemporalQuery currently carries). **CBR integration
  is deferred** — the `FromCbr` variant exists but TemporalIndex
  does not query CBR in this implementation. A follow-up can add
  `cbrDomain`/`cbrCaseType` to TemporalQuery when needed.
- Tests use direct instantiation (no CDI container) — inject stores
  directly via constructor. The `Instance<T>` fields can be set
  reflectively or via a test-visible constructor.

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryInput;
import io.casehub.neocortex.memory.inmem.InMemoryMemoryStore;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class TemporalIndexTest {

    private static final String TENANT = "test-tenant";
    private static final String AGENT = "agent-1";
    private static final Instant NOW = Instant.parse("2026-01-01T12:00:00Z");
    private static final Instant HOUR_AGO = NOW.minusSeconds(3600);
    private static final Instant TOMORROW = NOW.plusSeconds(86400);
    private static final MemoryDomain EXPERIENCE = new MemoryDomain("experience");
    private static final Confidence CONF = new Confidence(ConfidenceOrigin.STATED, 0.8, NOW);

    private InMemoryMindMapStore mindMapStore;
    private InMemoryMemoryStore memoryStore;
    private TemporalIndex index;

    @BeforeEach
    void setUp() {
        mindMapStore = new InMemoryMindMapStore();
        memoryStore = new InMemoryMemoryStore();
        index = new TemporalIndex(mindMapStore, memoryStore, null);
    }

    @Test
    void since_returnsMindMapNodesByUpdatedAt() {
        var nodeInput = new NodeInput("meeting", null, CONF, null, null, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, TENANT);

        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 50);
        var results = index.query(query);

        assertThat(results).hasSize(1);
        assertThat(results.getFirst().source()).isInstanceOf(TemporalSource.FromMindMap.class);
        assertThat(results.getFirst().tenantId()).isEqualTo(TENANT);
    }

    @Test
    void since_returnsMemoriesWithEntityIds() {
        memoryStore.store(new MemoryInput(AGENT, EXPERIENCE, TENANT, null, "test fact", Map.of(), CONF));

        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 50)
            .withEntityIds(List.of(AGENT));
        var results = index.query(query);

        assertThat(results)
            .anyMatch(e -> e.source() instanceof TemporalSource.FromMemory);
    }

    @Test
    void since_skipsMemoryWhenNoEntityIds() {
        memoryStore.store(new MemoryInput(AGENT, EXPERIENCE, TENANT, null, "test fact", Map.of(), CONF));

        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 50);
        var results = index.query(query);

        assertThat(results)
            .noneMatch(e -> e.source() instanceof TemporalSource.FromMemory);
    }

    @Test
    void upcoming_returnsFutureMindMapNodes() {
        var nodeInput = new NodeInput("future event", null, CONF, null, TOMORROW, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, TENANT);

        var query = TemporalQuery.upcoming(List.of(TENANT), NOW, 50);
        var results = index.query(query);

        assertThat(results).hasSize(1);
        assertThat(results.getFirst().timestamp()).isEqualTo(TOMORROW);
    }

    @Test
    void multiTenant_mergesResultsWithProvenance() {
        var nodeInput = new NodeInput("node-t1", null, CONF, null, null, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, "tenant-1");
        mindMapStore.addNode(nodeInput, "tenant-2");

        var query = TemporalQuery.since(List.of("tenant-1", "tenant-2"), HOUR_AGO, 50);
        var results = index.query(query);

        assertThat(results).hasSize(2);
        assertThat(results).extracting(TemporalEntry::tenantId)
            .containsExactlyInAnyOrder("tenant-1", "tenant-2");
    }

    @Test
    void resultsSortedChronologically() {
        memoryStore.store(new MemoryInput(AGENT, EXPERIENCE, TENANT, null, "first", Map.of(), CONF));
        memoryStore.store(new MemoryInput(AGENT, EXPERIENCE, TENANT, null, "second", Map.of(), CONF));
        var nodeInput = new NodeInput("node", null, CONF, null, null, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, TENANT);

        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 50)
            .withEntityIds(List.of(AGENT));
        var results = index.query(query);

        assertThat(results).isSortedAccordingTo(TemporalEntry::compareTo);
    }

    @Test
    void limit_trimsMergedResults() {
        for (int i = 0; i < 5; i++) {
            memoryStore.store(new MemoryInput(AGENT, EXPERIENCE, TENANT, null, "fact-" + i, Map.of(), CONF));
        }
        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 3)
            .withEntityIds(List.of(AGENT));
        var results = index.query(query);

        assertThat(results).hasSize(3);
    }

    @Test
    void emptyWindow_returnsNoResults() {
        var nodeInput = new NodeInput("node", null, CONF, null, null, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, TENANT);

        var farFuture = Instant.parse("2099-01-01T00:00:00Z");
        var query = TemporalQuery.window(List.of(TENANT), farFuture, farFuture.plusSeconds(3600), 50);
        var results = index.query(query);

        assertThat(results).isEmpty();
    }

    @Test
    void withSources_onlyQueriesRequestedStores() {
        memoryStore.store(new MemoryInput(AGENT, EXPERIENCE, TENANT, null, "fact", Map.of(), CONF));
        var nodeInput = new NodeInput("node", null, CONF, null, null, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, TENANT);

        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 50)
            .withEntityIds(List.of(AGENT))
            .withSources(java.util.Set.of(TemporalQuery.StoreKind.MEMORY));
        var results = index.query(query);

        assertThat(results)
            .allMatch(e -> e.source() instanceof TemporalSource.FromMemory);
    }

    @Test
    void missingStore_silentlySkipped() {
        var indexNoMemory = new TemporalIndex(mindMapStore, null, null);
        var nodeInput = new NodeInput("node", null, CONF, null, null, null, null, null, null, null, Map.of());
        mindMapStore.addNode(nodeInput, TENANT);

        var query = TemporalQuery.since(List.of(TENANT), HOUR_AGO, 50);
        var results = indexNoMemory.query(query);

        assertThat(results).hasSize(1);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=TemporalIndexTest`
Expected: FAIL — `TemporalIndex` doesn't exist

- [ ] **Step 3: Implement TemporalIndex**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryOrder;
import io.casehub.neocortex.memory.MemoryQuery;
import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapQuery;
import io.casehub.neocortex.mindmap.MindMapStore;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;

/**
 * Cross-store temporal aggregator — queries MindMap, Memory, and CBR stores
 * on demand and merges results into a single chronological timeline.
 *
 * <p>This is a <strong>stateless derived view</strong>, not a store. It holds
 * no persistent state and re-queries the underlying stores on every call.
 * All source data is owned by the originating stores — this class is pure
 * orchestration. The same architectural pattern as {@code MindMapAnalyzer}
 * and {@code RetrievalAnalyzer}.
 *
 * <p>Stores are injected via {@link Instance} for graceful degradation —
 * missing stores are silently skipped. An app using only MindMap gets
 * temporal indexing for MindMap nodes without pulling in memory backends.
 */
@ApplicationScoped
public class TemporalIndex {

    private static final MemoryDomain EXPERIENCE_DOMAIN = new MemoryDomain("experience");
    private static final Duration UPCOMING_TOLERANCE = Duration.ofSeconds(1);

    private final MindMapStore mindMapStore;
    private final CaseMemoryStore memoryStore;
    private final CbrCaseMemoryStore cbrStore;

    @Inject
    public TemporalIndex(Instance<MindMapStore> mindMapStore,
                         Instance<CaseMemoryStore> memoryStore,
                         Instance<CbrCaseMemoryStore> cbrStore) {
        this.mindMapStore = mindMapStore != null && mindMapStore.isResolvable() ? mindMapStore.get() : null;
        this.memoryStore = memoryStore != null && memoryStore.isResolvable() ? memoryStore.get() : null;
        this.cbrStore = cbrStore != null && cbrStore.isResolvable() ? cbrStore.get() : null;
    }

    /** Test constructor — inject stores directly. Null means unavailable. */
    TemporalIndex(MindMapStore mindMapStore, CaseMemoryStore memoryStore, CbrCaseMemoryStore cbrStore) {
        this.mindMapStore = mindMapStore;
        this.memoryStore = memoryStore;
        this.cbrStore = cbrStore;
    }

    public List<TemporalEntry> query(TemporalQuery query) {
        List<TemporalEntry> results = new ArrayList<>();

        if (query.sources().contains(TemporalQuery.StoreKind.MINDMAP) && mindMapStore != null) {
            results.addAll(queryMindMap(query));
        }

        if (query.sources().contains(TemporalQuery.StoreKind.MEMORY)
                && memoryStore != null && !query.entityIds().isEmpty()) {
            results.addAll(queryMemory(query));
        }

        Collections.sort(results);
        if (results.size() > query.limit()) {
            results = new ArrayList<>(results.subList(0, query.limit()));
        }
        return results;
    }

    private List<TemporalEntry> queryMindMap(TemporalQuery query) {
        List<TemporalEntry> entries = new ArrayList<>();
        boolean isUpcoming = isUpcomingQuery(query);

        for (String tenantId : query.tenantIds()) {
            MindMapQuery mmQuery;
            if (isUpcoming) {
                mmQuery = new MindMapQuery(tenantId, null, null, null, null,
                    null, null, false, query.from(), query.to(), null, query.limit());
            } else {
                mmQuery = new MindMapQuery(tenantId, null, null, null, null,
                    null, null, false, null, null, query.from(), query.limit());
            }

            List<MindMapNode> nodes = mindMapStore.search(mmQuery);
            for (MindMapNode node : nodes) {
                Instant timestamp = isUpcoming ? node.validFrom() : node.updatedAt();
                if (timestamp == null) continue;
                if (query.to() != null && !timestamp.isBefore(query.to())) continue;
                entries.add(new TemporalEntry(timestamp, new TemporalSource.FromMindMap(node),
                    tenantId, node.confidence()));
            }
        }
        return entries;
    }

    private List<TemporalEntry> queryMemory(TemporalQuery query) {
        List<TemporalEntry> entries = new ArrayList<>();

        for (String tenantId : query.tenantIds()) {
            MemoryQuery mq = MemoryQuery.forEntities(List.copyOf(query.entityIds()), EXPERIENCE_DOMAIN, tenantId)
                .withLimit(query.limit())
                .withOrder(MemoryOrder.CHRONOLOGICAL);
            if (query.from() != null) {
                mq = mq.withSince(query.from());
            }

            List<Memory> memories = memoryStore.query(mq);
            for (Memory memory : memories) {
                if (query.to() != null && memory.createdAt() != null
                        && !memory.createdAt().isBefore(query.to())) continue;
                Instant timestamp = memory.createdAt() != null ? memory.createdAt() : Instant.EPOCH;
                entries.add(new TemporalEntry(timestamp, new TemporalSource.FromMemory(memory),
                    tenantId, memory.confidence()));
            }
        }
        return entries;
    }

    private boolean isUpcomingQuery(TemporalQuery query) {
        if (query.from() == null) return false;
        Instant now = Instant.now();
        return !query.from().isBefore(now.minus(UPCOMING_TOLERANCE));
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=TemporalIndexTest`
Expected: PASS — all 10 tests green. Some tests may need adjustment
based on exact InMemoryMindMapStore and InMemoryMemoryStore constructor
signatures and NodeInput field ordering — fix any compilation issues.

- [ ] **Step 5: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS — all tests in the module green

- [ ] **Step 6: Commit**

```
git add cognitive-index/src/
git commit -m "feat(cognitive-index): TemporalIndex cross-store temporal aggregator

Stateless CDI bean that queries MindMap and Memory stores on demand,
merges results into a single chronological timeline. Graceful
degradation via Instance<T> — missing stores silently skipped.

Refs #237"
```

## Batch 3: Documentation + full build verification

### Task 5: Update CLAUDE.md and roadmap, verify full build

**Files:**
- Modify: `CLAUDE.md` — add cognitive-index module entry
- Modify: `docs/guides/cognitive-architecture-roadmap.md` — mark §2d DONE
- Modify: `docs/guides/consumer-guide.md` — add TemporalIndex section (if consumer-facing)

**Interfaces:**
- Consumes: nothing
- Produces: updated documentation

- [ ] **Step 1: Add cognitive-index to CLAUDE.md**

In the module structure section, add after `cognitive-api/`:
```
cognitive-index/    — cross-store cognitive query tier: TemporalIndex (chronological aggregation across MindMap + Memory + CBR), TemporalEntry, TemporalSource (sealed), TemporalQuery, TemporalRanker (@FunctionalInterface). Stateless derived view — re-queries stores on demand, no persistence. @ApplicationScoped CDI bean with Instance<T> graceful degradation. Growth path: CognitiveProfile (#243), TemporalFocus ranker (#244).
```

In the Maven Coordinates table, add:
```
| Cognitive Index | `casehub-neocortex-cognitive-index` |
```

And in the root Java package table:
```
| Root Java package (cognitive-index) | `io.casehub.neocortex.cognitive.index` |
```

- [ ] **Step 2: Mark §2d DONE in roadmap**

In `docs/guides/cognitive-architecture-roadmap.md`, update the §2d
heading to:

```
### 2d: Chronological Index — **DONE** (#237)
```

- [ ] **Step 3: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and tests pass

- [ ] **Step 4: Commit**

```
git add CLAUDE.md docs/
git commit -m "docs: add cognitive-index module, mark roadmap §2d DONE

Refs #237"
```

## References

- specs/issue-253-cognitive-rearchitecture/2026-08-31-chronological-index-design.md — design spec
- specs/issue-253-cognitive-rearchitecture/decisions.md — D12-D18
- cognitive-api/src/main/java/io/casehub/neocortex/cognitive/Confidence.java — shared type
- cognitive-api/src/main/java/io/casehub/neocortex/cognitive/TemporalMark.java — temporal type
- mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapQuery.java — temporal predicates (#236)
- mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java — search() SPI
- memory-api/src/main/java/io/casehub/neocortex/memory/MemoryQuery.java — since field, entityIds requirement
- memory-api/src/main/java/io/casehub/neocortex/memory/CaseMemoryStore.java — query() SPI
- docs/guides/cognitive-architecture-roadmap.md §2d — roadmap section
- GitHub #237 — focal issue
- GitHub #254 — follow-up: MemorySpace visibility layer wiring
