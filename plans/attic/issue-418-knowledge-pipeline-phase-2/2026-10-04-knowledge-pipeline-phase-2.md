# Knowledge Pipeline Phase 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #418 — epic: Knowledge Pipeline — Phase 2 follow-up
**Issue group:** #419, #420, #421, #422, #423, #426, #427

**Goal:** Complete the knowledge-pipeline module's implementation gaps, add CDI wiring, and improve test infrastructure.

**Architecture:** Seven issues executed in dependency order: refactor (#426) → contract tests (#427) → eviction hardening (#421) → resume TTL (#422) → subsumption wiring (#419) → staleness re-fetch (#420) → CDI wiring (#423). Each issue produces a self-contained, testable increment.

**Tech Stack:** Java 21, Quarkus 3.32.2, SQLite (HikariCP WAL), JUnit 5, AssertJ

## Global Constraints

- Java 21 language level, run on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Module test: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`
- Use `mvn` not `./mvnw`
- Every commit references an issue: `Refs #N` or `Closes #N`
- knowledge-pipeline depends on mindmap-intelligence (already in pom.xml)
- Flyway migrations in `src/main/resources/db/knowledge-pipeline/` (next: V3) and `db/knowledge-research/` (next: V2)
- `CachedEntity` record currently has 11 fields — will gain `detailFetchedAt` in Task 6
- `SpatialCacheStore` SPI currently has 7 methods — will gain `listAll` in Task 3 and `updateExpiry` in Task 4
- DB column `detail_fetched_at` already exists in `entity_metadata` table (V1__init.sql) — no Flyway migration needed for #420
- MindMapExtractor uses a cached variant of ensureSubgraph — excluded from #426

---

## Batch 1: Refactor + Test Infrastructure (#426, #427)

### Task 1: Extract SubgraphUtils to mindmap-intelligence (#426)

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubgraphUtils.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/SubgraphUtilsTest.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInService.java:93-100` (delete private method, update 3 call sites)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/promotion/EntityPromoter.java:100,132-139` (delete private method, update 1 call site)
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java:254-262,303-311` (delete 2 private methods, update 2 call sites)
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java:110-118` (delete private method, update 1 call site)

**Interfaces:**
- Produces: `SubgraphUtils.ensureSubgraph(MindMapStore store, String type, String tenantId) → String` (type used as both name and type)
- Produces: `SubgraphUtils.ensureSubgraph(MindMapStore store, String name, String type, String tenantId) → String` (explicit name)

- [ ] **Step 1: Write the failing test**

```java
// mindmap-intelligence/src/test/java/.../intelligence/SubgraphUtilsTest.java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SubgraphUtilsTest {

    private MindMapStore store;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
    }

    @Test
    void ensureSubgraphCreatesWhenAbsent() {
        String id = SubgraphUtils.ensureSubgraph(store, SubgraphTypes.PLACE, "t1");
        assertThat(id).isNotNull();
        assertThat(store.listSubgraphs("t1")).hasSize(1);
    }

    @Test
    void ensureSubgraphReusesExisting() {
        String first = SubgraphUtils.ensureSubgraph(store, SubgraphTypes.PLACE, "t1");
        String second = SubgraphUtils.ensureSubgraph(store, SubgraphTypes.PLACE, "t1");
        assertThat(second).isEqualTo(first);
        assertThat(store.listSubgraphs("t1")).hasSize(1);
    }

    @Test
    void ensureSubgraphDifferentTypesCreatesSeparate() {
        String place = SubgraphUtils.ensureSubgraph(store, SubgraphTypes.PLACE, "t1");
        String activity = SubgraphUtils.ensureSubgraph(store, SubgraphTypes.ACTIVITY, "t1");
        assertThat(place).isNotEqualTo(activity);
        assertThat(store.listSubgraphs("t1")).hasSize(2);
    }

    @Test
    void ensureSubgraphWithExplicitName() {
        String id = SubgraphUtils.ensureSubgraph(store, "Cognitive", SubgraphTypes.COGNITIVE, "t1");
        assertThat(id).isNotNull();
        var sg = store.listSubgraphs("t1").get(0);
        assertThat(sg.type()).isEqualTo(SubgraphTypes.COGNITIVE);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SubgraphUtilsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `SubgraphUtils` does not exist

- [ ] **Step 3: Create SubgraphUtils**

Use `ide_create_file` to create:

```java
// mindmap-intelligence/src/main/java/.../intelligence/SubgraphUtils.java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.MindMapSubgraph;
import io.casehub.neocortex.mindmap.SubgraphInput;

public final class SubgraphUtils {

    private SubgraphUtils() {}

    public static String ensureSubgraph(MindMapStore store, String type, String tenantId) {
        return ensureSubgraph(store, type, type, tenantId);
    }

    public static String ensureSubgraph(MindMapStore store, String name, String type,
                                         String tenantId) {
        return store.listSubgraphs(tenantId).stream()
            .filter(s -> type.equals(s.type()))
            .map(MindMapSubgraph::id)
            .findFirst()
            .orElseGet(() -> store.createSubgraph(
                new SubgraphInput(name, type, null), tenantId));
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SubgraphUtilsTest`
Expected: 4 tests PASS

- [ ] **Step 5: Update call sites**

Use `ide_replace_member` or Edit tool to update each class:

**CheckInService** — replace private `ensureSubgraph` method with import + static calls:
- Remove lines 93-100 (private method)
- Add import: `import static io.casehub.neocortex.mindmap.intelligence.SubgraphUtils.ensureSubgraph;`
- Update 3 call sites (lines 35, 49, 70) from `ensureSubgraph(type, tenantId)` to `ensureSubgraph(store, type, tenantId)` (adding `store` param — the field is named `store` in CheckInService)

**EntityPromoter** — same pattern:
- Remove lines 132-139 (private method)
- Add import: `import static io.casehub.neocortex.mindmap.intelligence.SubgraphUtils.ensureSubgraph;`
- Update line 100 from `ensureSubgraph(SubgraphTypes.PLACE, tenantId)` to `SubgraphUtils.ensureSubgraph(mindMapStore, SubgraphTypes.PLACE, tenantId)` (field is `mindMapStore`)

**ExperienceConsolidationPhase** — two private methods:
- Remove `findOrCreateCognitiveSubgraph` (lines 254-262)
- Remove `findOrCreateTypeSystemSubgraph` (lines 303-311)
- Add import: `import io.casehub.neocortex.mindmap.intelligence.SubgraphUtils;`
- Replace calls with `SubgraphUtils.ensureSubgraph(mindMapStore, "Cognitive", SubgraphTypes.COGNITIVE, tenantId)` and `SubgraphUtils.ensureSubgraph(mindMapStore, "Type System", SubgraphTypes.TYPE_SYSTEM, tenantId)`

**ConversationBridge** — one private method:
- Remove `findOrCreateGeneralSubgraph` (lines 110-118)
- Add import: `import io.casehub.neocortex.mindmap.intelligence.SubgraphUtils;`
- Replace call with `SubgraphUtils.ensureSubgraph(store, "General", SubgraphTypes.GENERAL, tenantId)`

- [ ] **Step 6: Run full module tests to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence,knowledge-pipeline`
Expected: all existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src knowledge-pipeline/src
git commit -m "refactor(#426): extract SubgraphUtils.ensureSubgraph to mindmap-intelligence

Consolidate find-or-create-subgraph pattern from CheckInService,
EntityPromoter, ExperienceConsolidationPhase, and ConversationBridge
into a shared static utility. No behavioral change.

Closes #426

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: Contract test abstract bases (#427)

**Files:**
- Create: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/testing/SpatialCacheStoreContractTest.java`
- Create: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/testing/EntityMatcherContractTest.java`
- Create: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/testing/ResearchSessionStoreContractTest.java`
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/InMemorySpatialCacheStoreTest.java` (becomes thin subclass)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/SqliteSpatialCacheStoreTest.java` (becomes thin subclass)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/resolution/PlaceMatcherTest.java` (becomes thin subclass)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/research/ResearchSessionStoreTest.java` (becomes thin subclass)

**Interfaces:**
- Produces: `SpatialCacheStoreContractTest` with `abstract SpatialCacheStore createStore()`
- Produces: `EntityMatcherContractTest` with `abstract EntityMatcher createMatcher()`
- Produces: `ResearchSessionStoreContractTest` with `abstract ResearchSessionStore createStore()` and `abstract void closeStore(ResearchSessionStore store)`

- [ ] **Step 1: Create SpatialCacheStoreContractTest**

Extract test methods from `InMemorySpatialCacheStoreTest` into the abstract base:

```java
// knowledge-pipeline/src/test/java/.../knowledge/testing/SpatialCacheStoreContractTest.java
package io.casehub.neocortex.knowledge.testing;

import io.casehub.connectors.location.model.Coordinates;
import io.casehub.neocortex.knowledge.BoundingBox;
import io.casehub.neocortex.knowledge.CacheFilter;
import io.casehub.neocortex.knowledge.CachedEntity;
import io.casehub.neocortex.knowledge.SpatialCacheStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

public abstract class SpatialCacheStoreContractTest {

    protected SpatialCacheStore store;

    protected abstract SpatialCacheStore createStore();

    @BeforeEach
    void setUp() {
        store = createStore();
    }

    protected CachedEntity entity(String id, double lat, double lng) {
        return new CachedEntity(id, "Place " + id, new Coordinates(lat, lng),
            "restaurant", "google", "ext-" + id, Map.of(),
            Instant.now(), Instant.now().plusSeconds(86400), Set.of(), false);
    }

    @Test
    void setAndGetRoundTrips() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        assertThat(store.get("e1", "t1")).isNotNull();
        assertThat(store.get("e1", "t1").name()).isEqualTo("Place e1");
    }

    @Test
    void getReturnsNullForUnknown() {
        assertThat(store.get("nonexistent", "t1")).isNull();
    }

    @Test
    void nearbyReturnsEntitiesWithinRadius() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        store.set(entity("e2", 51.50005, -0.10005), "t1");
        store.set(entity("e3", 55.9, -3.1), "t1");

        var nearby = store.nearby(new Coordinates(51.5, -0.1), 1000,
            CacheFilter.none(), "t1");
        assertThat(nearby).extracting(CachedEntity::id)
            .containsExactlyInAnyOrder("e1", "e2");
    }

    @Test
    void withinReturnsBoundedEntities() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        store.set(entity("e2", 51.6, -0.2), "t1");
        store.set(entity("e3", 55.9, -3.1), "t1");

        var within = store.within(
            new BoundingBox(51.4, -0.3, 51.7, 0.0), CacheFilter.none(), "t1");
        assertThat(within).extracting(CachedEntity::id)
            .containsExactlyInAnyOrder("e1", "e2");
    }

    @Test
    void removeDeletesEntity() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        store.remove("e1", "t1");
        assertThat(store.get("e1", "t1")).isNull();
    }

    @Test
    void expireUpdatesExpiresAt() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        Instant newExpiry = Instant.now().plusSeconds(999999);
        store.expire("e1", newExpiry, "t1");
        assertThat(store.get("e1", "t1").expiresAt()).isEqualTo(newExpiry);
    }

    @Test
    void tenantIsolation() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        store.set(entity("e2", 51.5, -0.1), "t2");
        assertThat(store.get("e1", "t2")).isNull();
        assertThat(store.get("e2", "t1")).isNull();
    }

    @Test
    void nearbyFiltersByCategory() {
        var italian = new CachedEntity("e1", "Ondine", new Coordinates(51.5, -0.1),
            "italian", "google", "ext-1", Map.of(),
            Instant.now(), Instant.now().plusSeconds(86400), Set.of(), false);
        var coffee = new CachedEntity("e2", "Costa", new Coordinates(51.50001, -0.10001),
            "coffee", "google", "ext-2", Map.of(),
            Instant.now(), Instant.now().plusSeconds(86400), Set.of(), false);
        store.set(italian, "t1");
        store.set(coffee, "t1");

        var filtered = store.nearby(new Coordinates(51.5, -0.1), 1000,
            new CacheFilter("italian", null, null, null), "t1");
        assertThat(filtered).extracting(CachedEntity::id).containsExactly("e1");
    }

    @Test
    void findExpiredReturnsExpiredEntities() {
        var expired = new CachedEntity("e1", "Old", new Coordinates(51.5, -0.1),
            "restaurant", "google", "ext-1", Map.of(),
            Instant.now().minusSeconds(86400), Instant.now().minusSeconds(1), Set.of(), false);
        store.set(expired, "t1");
        assertThat(store.findExpired("t1", Instant.now())).contains("e1");
    }

    @Test
    void discoverTenantsReturnsAllTenants() {
        store.set(entity("e1", 51.5, -0.1), "t1");
        store.set(entity("e2", 51.5, -0.1), "t2");
        assertThat(store.discoverTenants()).containsExactlyInAnyOrder("t1", "t2");
    }
}
```

- [ ] **Step 2: Convert InMemorySpatialCacheStoreTest to thin subclass**

```java
package io.casehub.neocortex.knowledge.cache;

import io.casehub.neocortex.knowledge.SpatialCacheStore;
import io.casehub.neocortex.knowledge.testing.SpatialCacheStoreContractTest;

class InMemorySpatialCacheStoreTest extends SpatialCacheStoreContractTest {

    @Override
    protected SpatialCacheStore createStore() {
        return new InMemorySpatialCacheStore();
    }
}
```

- [ ] **Step 3: Convert SqliteSpatialCacheStoreTest to thin subclass**

Read existing `SqliteSpatialCacheStoreTest` first. Then make it extend the contract test, keeping any SQLite-specific tests (e.g., R*Tree behavior) as additional methods.

- [ ] **Step 4: Create EntityMatcherContractTest**

```java
package io.casehub.neocortex.knowledge.testing;

import io.casehub.connectors.location.model.Coordinates;
import io.casehub.neocortex.knowledge.CachedEntity;
import io.casehub.neocortex.knowledge.EntityMatcher;
import io.casehub.neocortex.knowledge.MatchTier;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

public abstract class EntityMatcherContractTest {

    protected abstract EntityMatcher<CachedEntity> createMatcher();

    protected CachedEntity entity(String id, String name, double lat, double lng,
                                   String source, String extId, Map<String, String> props) {
        return new CachedEntity(id, name, new Coordinates(lat, lng), "restaurant",
            source, extId, props, Instant.now(),
            Instant.now().plusSeconds(86400), Set.of(), false);
    }

    @Test
    void sameExternalIdIsDefinitive() {
        var matcher = createMatcher();
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "ChIJ123", Map.of());
        var b = entity("2", "Ondine Seafood", 51.5001, -0.1001, "google", "ChIJ123", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.tier()).isEqualTo(MatchTier.DEFINITIVE);
    }

    @Test
    void closeProximityAndSimilarNameMatches() {
        var matcher = createMatcher();
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1", Map.of());
        var b = entity("2", "Ondine Restaurant", 51.50003, -0.10003, "tripadvisor", "t1", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.confidence()).isGreaterThanOrEqualTo(0.65);
    }

    @Test
    void distantEntitiesAreNoMatch() {
        var matcher = createMatcher();
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1", Map.of());
        var b = entity("2", "Ondine", 55.9, -3.1, "tripadvisor", "t1", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.tier()).isEqualTo(MatchTier.LOW);
    }

    @Test
    void noMatchingSignalsReturnsLow() {
        var matcher = createMatcher();
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1", Map.of());
        var b = entity("2", "Costa Coffee", 51.5005, -0.1005, "tripadvisor", "t1", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.tier()).isEqualTo(MatchTier.LOW);
    }
}
```

- [ ] **Step 5: Convert PlaceMatcherTest to extend contract test**

Keep PlaceMatcher-specific tests (phone matching, different-source checks) as additional methods.

```java
package io.casehub.neocortex.knowledge.resolution;

import io.casehub.neocortex.knowledge.EntityMatcher;
import io.casehub.neocortex.knowledge.MatchTier;
import io.casehub.neocortex.knowledge.testing.EntityMatcherContractTest;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class PlaceMatcherTest extends EntityMatcherContractTest {

    @Override
    protected EntityMatcher<CachedEntity> createMatcher() {
        return new PlaceMatcher();
    }

    @Test
    void phoneMatchIsHigh() {
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1",
            Map.of("phone", "+44 131 226 1888"));
        var b = entity("2", "Ondine Seafood", 51.50003, -0.10003, "tripadvisor", "t1",
            Map.of("phone", "0131 226 1888"));
        var result = createMatcher().match(a, b);
        assertThat(result.tier()).isIn(MatchTier.DEFINITIVE, MatchTier.HIGH);
    }

    @Test
    void differentSourcesSameExternalIdIsNotDefinitive() {
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "123", Map.of());
        var b = entity("2", "Ondine", 51.5, -0.1, "tripadvisor", "123", Map.of());
        var result = createMatcher().match(a, b);
        assertThat(result.tier()).isNotEqualTo(MatchTier.DEFINITIVE);
    }
}
```

- [ ] **Step 6: Create ResearchSessionStoreContractTest and convert existing test**

```java
package io.casehub.neocortex.knowledge.testing;

import io.casehub.neocortex.knowledge.ResearchSession;
import io.casehub.neocortex.knowledge.ResearchState;
import io.casehub.neocortex.knowledge.research.ResearchSessionStore;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

public abstract class ResearchSessionStoreContractTest {

    protected ResearchSessionStore store;

    protected abstract ResearchSessionStore createStore();
    protected void closeStore(ResearchSessionStore store) {}

    @BeforeEach
    void setUp() {
        store = createStore();
    }

    @AfterEach
    void tearDown() {
        closeStore(store);
    }

    protected ResearchSession testSession(String id, String tenantId) {
        return new ResearchSession(id, "Edinburgh trip",
            "{\"maxPrice\":150}", "sg-1", ResearchState.ACTIVE,
            tenantId, Instant.now(), Instant.now());
    }

    @Test
    void insertAndGetRoundTrips() {
        store.insert(testSession("s1", "t1"));
        var session = store.get("s1");
        assertThat(session).isPresent();
        assertThat(session.get().name()).isEqualTo("Edinburgh trip");
        assertThat(session.get().state()).isEqualTo(ResearchState.ACTIVE);
    }

    @Test
    void getReturnsEmptyForUnknown() {
        assertThat(store.get("nonexistent")).isEmpty();
    }

    @Test
    void updateStateChangesStateAndLastActive() {
        store.insert(testSession("s1", "t1"));
        Instant newTime = Instant.now().plusSeconds(10);
        store.updateState("s1", ResearchState.PAUSED, newTime);
        var session = store.get("s1").get();
        assertThat(session.state()).isEqualTo(ResearchState.PAUSED);
        assertThat(session.lastActive()).isEqualTo(newTime);
    }

    @Test
    void listByStateFiltersCorrectly() {
        store.insert(testSession("s1", "t1"));
        store.insert(testSession("s2", "t1"));
        store.updateState("s2", ResearchState.PAUSED, Instant.now());
        var active = store.listByState("t1", ResearchState.ACTIVE);
        assertThat(active).hasSize(1);
        assertThat(active.get(0).id()).isEqualTo("s1");
    }

    @Test
    void listByStateTenantIsolation() {
        store.insert(testSession("s1", "t1"));
        store.insert(testSession("s2", "t2"));
        assertThat(store.listByState("t1", ResearchState.ACTIVE)).hasSize(1);
        assertThat(store.listByState("t2", ResearchState.ACTIVE)).hasSize(1);
    }

    @Test
    void fullStateTransitionLifecycle() {
        store.insert(testSession("s1", "t1"));
        store.updateState("s1", ResearchState.PAUSED, Instant.now());
        store.updateState("s1", ResearchState.ACTIVE, Instant.now());
        store.updateState("s1", ResearchState.COMPLETED, Instant.now());
        assertThat(store.get("s1").get().state()).isEqualTo(ResearchState.COMPLETED);
        assertThat(store.listByState("t1", ResearchState.ACTIVE)).isEmpty();
    }
}
```

Convert `ResearchSessionStoreTest`:

```java
package io.casehub.neocortex.knowledge.research;

import io.casehub.neocortex.knowledge.testing.ResearchSessionStoreContractTest;

class ResearchSessionStoreTest extends ResearchSessionStoreContractTest {

    @Override
    protected ResearchSessionStore createStore() {
        return new ResearchSessionStore(":memory:");
    }

    @Override
    protected void closeStore(ResearchSessionStore store) {
        store.close();
    }
}
```

- [ ] **Step 7: Run all knowledge-pipeline tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline`
Expected: all tests PASS (same tests, now via contract bases)

- [ ] **Step 8: Commit**

```bash
git add knowledge-pipeline/src/test
git commit -m "test(#427): add contract test abstract bases for SpatialCacheStore, EntityMatcher, ResearchSessionStore

Extract existing test logic into reusable abstract bases.
InMemorySpatialCacheStoreTest, SqliteSpatialCacheStoreTest,
PlaceMatcherTest, and ResearchSessionStoreTest become thin subclasses.

Closes #427

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 2: Eviction Hardening + Resume TTL (#421, #422)

### Task 3: Max entity age + session auto-complete (#421)

**Files:**
- Modify: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/SpatialCacheStore.java` (add `listAll` method)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/CacheEvictionScheduler.java` (add 2 constructor params, 2 new phases)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/InMemorySpatialCacheStore.java` (implement `listAll`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/SqliteSpatialCacheStore.java` (implement `listAll`)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/CacheEvictionSchedulerTest.java` (add tests)
- Test: existing `CacheEvictionSchedulerTest`

**Interfaces:**
- Consumes: `ResearchSessionStore.listByState(tenantId, state)`, `ResearchSession.createdAt()`
- Produces: `SpatialCacheStore.listAll(String tenantId) → List<CachedEntity>` (new SPI method, reused by Task 6)

- [ ] **Step 1: Add listAll to SpatialCacheStore SPI**

```java
// In SpatialCacheStore.java, add:
List<CachedEntity> listAll(String tenantId);
```

- [ ] **Step 2: Implement listAll in InMemorySpatialCacheStore**

```java
@Override
public List<CachedEntity> listAll(String tenantId) {
    var entities = tenants.get(tenantId);
    if (entities == null) return List.of();
    return List.copyOf(entities.values());
}
```

- [ ] **Step 3: Implement listAll in SqliteSpatialCacheStore**

```java
@Override
public List<CachedEntity> listAll(String tenantId) {
    try (Connection c = ds.getConnection();
         PreparedStatement ps = c.prepareStatement(
             "SELECT * FROM entity_metadata WHERE tenant_id = ?")) {
        ps.setString(1, tenantId);
        ResultSet rs = ps.executeQuery();
        List<CachedEntity> results = new ArrayList<>();
        while (rs.next()) {
            results.add(mapRow(rs));
        }
        return results;
    } catch (SQLException e) {
        throw new RuntimeException(e);
    }
}
```

- [ ] **Step 4: Write tests for session auto-complete and max entity age**

```java
// In CacheEvictionSchedulerTest.java, add:
@Test
void autoCompletesSessionsPastMaxDuration() {
    Instant old = Instant.now().minus(Duration.ofDays(200));
    sessionStore.insert(new ResearchSession("s1", "test", "{}", "sg-1",
        ResearchState.ACTIVE, "t1", old, old));
    store.set(entity("e1", 51.5, -0.1), "t1");
    metadataStore.addSession("e1", "s1");

    scheduler.runEviction();

    assertThat(sessionStore.get("s1").get().state()).isEqualTo(ResearchState.COMPLETED);
}

@Test
void evictsEntitiesPastMaxAge() {
    var ancient = new CachedEntity("e1", "Old Place", new Coordinates(51.5, -0.1),
        "restaurant", "google", "ext-1", Map.of(),
        Instant.now().minus(Duration.ofDays(100)),
        Instant.now().plusSeconds(86400), Set.of("s1"), false);
    store.set(ancient, "t1");
    // Session is active — normally would protect entity
    sessionStore.insert(new ResearchSession("s1", "test", "{}", "sg-1",
        ResearchState.ACTIVE, "t1", Instant.now(), Instant.now()));
    metadataStore.addSession("e1", "s1");

    scheduler.runEviction();

    assertThat(store.get("e1", "t1")).isNull();
}
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=CacheEvictionSchedulerTest`
Expected: new tests FAIL

- [ ] **Step 6: Implement session auto-complete and max age eviction**

Update `CacheEvictionScheduler` constructor to accept `Duration maxEntityAge` and `Duration maxSessionDuration`. Add to `evictForTenant`:

```java
// Phase 1: auto-complete stale sessions
private void autoCompleteStaleSessions(String tenantId, Instant now) {
    for (ResearchState state : List.of(ResearchState.ACTIVE, ResearchState.PAUSED)) {
        for (ResearchSession session : sessionStore.listByState(tenantId, state)) {
            if (session.createdAt().plus(maxSessionDuration).isBefore(now)) {
                sessionStore.updateState(session.id(), ResearchState.COMPLETED, now);
                LOG.info("Auto-completed session " + session.id()
                    + " (age: " + Duration.between(session.createdAt(), now).toDays() + "d)");
            }
        }
    }
}

// Phase 2 addition: age cap eviction after existing expired-entity loop
private void evictByAge(String tenantId, Instant now) {
    Instant cutoff = now.minus(maxEntityAge);
    List<CachedEntity> all = cacheStore.listAll(tenantId);
    int evicted = 0;
    for (CachedEntity entity : all) {
        if (entity.fetchedAt() != null && entity.fetchedAt().isBefore(cutoff)) {
            cacheStore.remove(entity.id(), tenantId);
            metadataStore.delete(entity.id());
            evicted++;
        }
    }
    if (evicted > 0) {
        LOG.info("Age-cap eviction for tenant " + tenantId + ": evicted=" + evicted);
    }
}
```

Call `autoCompleteStaleSessions` at the start of `evictForTenant`, then `evictByAge` after the existing loop.

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=CacheEvictionSchedulerTest`
Expected: all tests PASS

- [ ] **Step 8: Update existing callers of CacheEvictionScheduler constructor**

Check `KnowledgePipelineOrchestratorTest` and `KnowledgePipelineIntegrationTest` — update constructor calls to pass `Duration.ofDays(90)` and `Duration.ofDays(180)` as defaults.

- [ ] **Step 9: Run full module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline`
Expected: all tests PASS

- [ ] **Step 10: Commit**

```bash
git add knowledge-pipeline-api/src knowledge-pipeline/src
git commit -m "feat(#421): enforce max entity age and session auto-complete in CacheEvictionScheduler

Add SpatialCacheStore.listAll() SPI method. CacheEvictionScheduler now
auto-completes sessions past maxSessionDuration (default 180d) and
evicts entities past maxEntityAge (default 90d) regardless of session
protection.

Closes #421

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: Resume TTL extension (#422)

**Files:**
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/EntityMetadataStore.java` (add `entitiesForSession`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/research/ResearchOrchestrator.java` (add 3 constructor deps, update `resume`)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/EntityMetadataStoreTest.java` (add test)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/research/ResearchOrchestratorTest.java` (add test)

**Interfaces:**
- Consumes: `SpatialCacheStore.expire(entityId, expiresAt, tenantId)` (existing), `CacheDecayPolicy.ttlFor(entity)` (existing), `EntityMetadataStore.sessionsFor(entityId)` (existing)
- Produces: `EntityMetadataStore.entitiesForSession(String sessionId) → Set<String>` (new method)

- [ ] **Step 1: Write test for entitiesForSession**

```java
// In EntityMetadataStoreTest.java, add:
@Test
void entitiesForSessionReturnsEntityIds() {
    metadataStore.addSession("e1", "s1");
    metadataStore.addSession("e2", "s1");
    metadataStore.addSession("e3", "s2");

    Set<String> entities = metadataStore.entitiesForSession("s1");
    assertThat(entities).containsExactlyInAnyOrder("e1", "e2");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=EntityMetadataStoreTest#entitiesForSessionReturnsEntityIds`
Expected: FAIL — method does not exist

- [ ] **Step 3: Implement entitiesForSession**

```java
// In EntityMetadataStore.java, add:
public Set<String> entitiesForSession(String sessionId) {
    try (Connection c = ds.getConnection();
         PreparedStatement ps = c.prepareStatement(
             "SELECT entity_id FROM entity_sessions WHERE session_id = ?")) {
        ps.setString(1, sessionId);
        ResultSet rs = ps.executeQuery();
        var entities = new LinkedHashSet<String>();
        while (rs.next()) entities.add(rs.getString("entity_id"));
        return entities;
    } catch (SQLException e) { throw new RuntimeException(e); }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=EntityMetadataStoreTest#entitiesForSessionReturnsEntityIds`
Expected: PASS

- [ ] **Step 5: Write test for resume TTL extension**

```java
// In ResearchOrchestratorTest.java, add:
@Test
void resumeExtendsTtlForSessionEntities() {
    orchestrator.create("Test", "{}", "t1");
    var sessions = sessionStore.listByState("t1", ResearchState.ACTIVE);
    String sessionId = sessions.get(0).id();

    // Set up an entity linked to this session with short expiry
    Instant shortExpiry = Instant.now().plusSeconds(60);
    var entity = new CachedEntity("e1", "Place", new Coordinates(51.5, -0.1),
        "restaurant", "google", "ext-1", Map.of(),
        Instant.now(), shortExpiry, Set.of(), false);
    cacheStore.set(entity, "t1");
    metadataStore.addSession("e1", sessionId);

    orchestrator.pause(sessionId);
    orchestrator.resume(sessionId);

    CachedEntity updated = cacheStore.get("e1", "t1");
    assertThat(updated.expiresAt()).isAfter(shortExpiry);
}
```

- [ ] **Step 6: Run test to verify it fails**

Expected: FAIL — resume doesn't extend TTL yet

- [ ] **Step 7: Implement resume TTL extension**

Update `ResearchOrchestrator` constructor to add `SpatialCacheStore`, `EntityMetadataStore`, and `CacheDecayPolicy` parameters. Update `resume`:

```java
@Override
public void resume(String sessionId) {
    sessionStore.updateState(sessionId, ResearchState.ACTIVE, Instant.now());
    var session = sessionStore.get(sessionId);
    if (session.isEmpty()) return;
    Instant now = Instant.now();
    Set<String> entityIds = metadataStore.entitiesForSession(sessionId);
    for (String entityId : entityIds) {
        CachedEntity entity = cacheStore.get(entityId, session.get().tenantId());
        if (entity != null) {
            Instant newExpiry = now.plus(decayPolicy.ttlFor(entity));
            cacheStore.expire(entityId, newExpiry, session.get().tenantId());
        }
    }
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=ResearchOrchestratorTest`
Expected: all tests PASS

- [ ] **Step 9: Update existing ResearchOrchestrator constructor calls in tests**

Update `ResearchOrchestratorTest` and any integration test to pass the new dependencies.

- [ ] **Step 10: Run full module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline`
Expected: all tests PASS

- [ ] **Step 11: Commit**

```bash
git add knowledge-pipeline/src
git commit -m "feat(#422): implement resume TTL extension in ResearchOrchestrator

On resume, recompute expiresAt for all session entities via
CacheDecayPolicy.ttlFor(). Add EntityMetadataStore.entitiesForSession()
inverse lookup.

Closes #422

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 3: Subsumption + Staleness (#419, #420)

### Task 5: Wire SubsumptionRule into orchestrator search flow (#419)

**Files:**
- Create: `knowledge-pipeline/src/main/resources/db/knowledge-pipeline/V3__query_cache_params.sql`
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/QueryCacheStore.java` (add columns to record(), add listForTenant(), extend QueryCacheEntry)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestrator.java` (add SubsumptionRule param, add subsumption scan)
- Modify: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestratorTest.java` (add subsumption tests)
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/QueryCacheStoreTest.java` (add listForTenant test)

**Interfaces:**
- Consumes: `SubsumptionRule.subsume(query, broaderResults, broaderQuery)` (existing SPI), `SpatialSubsumptionRule` (existing impl), `CacheKeyGenerator.generate()` (existing)
- Produces: `QueryCacheStore.listForTenant(String tenantId) → List<QueryCacheEntry>`, `QueryCacheEntry.toNormalizedQuery() → NormalizedQuery`

- [ ] **Step 1: Create Flyway migration V3**

```sql
-- V3__query_cache_params.sql
ALTER TABLE query_cache ADD COLUMN query_type TEXT;
ALTER TABLE query_cache ADD COLUMN lat REAL;
ALTER TABLE query_cache ADD COLUMN lng REAL;
ALTER TABLE query_cache ADD COLUMN radius_meters INTEGER;
ALTER TABLE query_cache ADD COLUMN category TEXT;
```

- [ ] **Step 2: Write test for QueryCacheStore.listForTenant**

```java
// In QueryCacheStoreTest.java, add:
@Test
void listForTenantReturnsNonExpiredEntries() {
    Instant future = Instant.now().plusSeconds(86400);
    store.record("NEARBY:abc:500", "t1", List.of("e1"),
        future, "NEARBY", 51.5, -0.1, 500, null);
    store.record("CATEGORY:restaurant:abc:1000", "t1", List.of("e2"),
        future, "CATEGORY", 51.5, -0.1, 1000, "restaurant");
    store.record("TEXT:coffee", "t1", List.of("e3"),
        future, "TEXT", null, null, null, null);

    var entries = store.listForTenant("t1");
    assertThat(entries).hasSize(3);
}

@Test
void listForTenantExcludesExpired() {
    Instant past = Instant.now().minusSeconds(1);
    store.record("NEARBY:abc:500", "t1", List.of("e1"),
        past, "NEARBY", 51.5, -0.1, 500, null);

    var entries = store.listForTenant("t1");
    assertThat(entries).isEmpty();
}

@Test
void queryEntryReconstructsNormalizedQuery() {
    Instant future = Instant.now().plusSeconds(86400);
    store.record("NEARBY:abc:500", "t1", List.of("e1"),
        future, "NEARBY", 51.5, -0.1, 500, null);

    var entries = store.listForTenant("t1");
    NormalizedQuery nq = entries.get(0).toNormalizedQuery();
    assertThat(nq.query()).isInstanceOf(KnowledgeQuery.NearbySearch.class);
    var nearby = (KnowledgeQuery.NearbySearch) nq.query();
    assertThat(nearby.center().lat()).isEqualTo(51.5);
    assertThat(nearby.radiusMeters()).isEqualTo(500);
}
```

- [ ] **Step 3: Run tests to verify they fail**

Expected: FAIL — overloaded `record()` and `listForTenant()` don't exist

- [ ] **Step 4: Implement QueryCacheStore changes**

Update `record()` to accept query parameters and store them. Add `listForTenant()`:

```java
public void record(String cacheKey, String tenantId, List<String> entityIds,
                    Instant expiresAt, String queryType,
                    Double lat, Double lng, Integer radiusMeters, String category) {
    String now = Instant.now().toString();
    String idsJson = serializeEntityIds(entityIds);
    try (Connection c = ds.getConnection();
         PreparedStatement ps = c.prepareStatement(
             "INSERT OR REPLACE INTO query_cache "
             + "(cache_key, tenant_id, entity_ids, answered_at, expires_at, "
             + "query_type, lat, lng, radius_meters, category) "
             + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")) {
        ps.setString(1, cacheKey);
        ps.setString(2, tenantId);
        ps.setString(3, idsJson);
        ps.setString(4, now);
        ps.setString(5, expiresAt.toString());
        ps.setString(6, queryType);
        if (lat != null) ps.setDouble(7, lat); else ps.setNull(7, java.sql.Types.REAL);
        if (lng != null) ps.setDouble(8, lng); else ps.setNull(8, java.sql.Types.REAL);
        if (radiusMeters != null) ps.setInt(9, radiusMeters); else ps.setNull(9, java.sql.Types.INTEGER);
        ps.setString(10, category);
        ps.executeUpdate();
    } catch (SQLException e) { throw new RuntimeException(e); }
}

public List<QueryCacheEntry> listForTenant(String tenantId) {
    try (Connection c = ds.getConnection();
         PreparedStatement ps = c.prepareStatement(
             "SELECT * FROM query_cache WHERE tenant_id = ? AND expires_at > ?")) {
        ps.setString(1, tenantId);
        ps.setString(2, Instant.now().toString());
        ResultSet rs = ps.executeQuery();
        List<QueryCacheEntry> entries = new ArrayList<>();
        while (rs.next()) {
            entries.add(new QueryCacheEntry(
                rs.getString("cache_key"), rs.getString("tenant_id"),
                parseEntityIds(rs.getString("entity_ids")),
                Instant.parse(rs.getString("answered_at")),
                Instant.parse(rs.getString("expires_at")),
                rs.getString("query_type"),
                rs.getObject("lat") != null ? rs.getDouble("lat") : null,
                rs.getObject("lng") != null ? rs.getDouble("lng") : null,
                rs.getObject("radius_meters") != null ? rs.getInt("radius_meters") : null,
                rs.getString("category")));
        }
        return entries;
    } catch (SQLException e) { throw new RuntimeException(e); }
}
```

Extend `QueryCacheEntry` to include query parameters and add `toNormalizedQuery()`:

```java
public record QueryCacheEntry(String cacheKey, String tenantId,
                               List<String> entityIds, Instant answeredAt,
                               Instant expiresAt, String queryType,
                               Double lat, Double lng, Integer radiusMeters,
                               String category) {

    public NormalizedQuery toNormalizedQuery() {
        KnowledgeQuery query = switch (queryType) {
            case "TEXT" -> new KnowledgeQuery.TextSearch(
                cacheKey.substring("TEXT:".length()));
            case "NEARBY" -> new KnowledgeQuery.NearbySearch(
                new Coordinates(lat, lng), radiusMeters, null);
            case "CATEGORY" -> new KnowledgeQuery.CategorySearch(
                category, new Coordinates(lat, lng), radiusMeters);
            default -> throw new IllegalStateException("Unknown query type: " + queryType);
        };
        return new NormalizedQuery(query, cacheKey);
    }
}
```

- [ ] **Step 5: Run QueryCacheStore tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=QueryCacheStoreTest`
Expected: PASS

- [ ] **Step 6: Write test for subsumption scan in orchestrator**

```java
// In KnowledgePipelineOrchestratorTest.java, add:
@Test
void subsumptionReturnsFilteredSubsetFromBroaderQuery() {
    // Pre-populate cache with a broad nearby query (2000m radius)
    // Then search with a narrow nearby query (500m radius) within the broad area
    // Should return entities filtered from the broader result without hitting providers
}
```

Implement the test body using the existing test patterns (stub LocationPlatform, pre-populate query cache with broad results, verify narrow query returns subset without provider call).

- [ ] **Step 7: Implement subsumption scan in orchestrator**

Update `KnowledgePipelineOrchestrator` constructor to add `SubsumptionRule` parameter. Add subsumption scan between exact cache hit and provider fetch in `search()`:

```java
// After exact cache miss, before provider fetch:
List<QueryCacheStore.QueryCacheEntry> cached = queryCache.listForTenant(tenantId);
for (var entry : cached) {
    NormalizedQuery broaderNormalized = entry.toNormalizedQuery();
    List<CachedEntity> broaderEntities = new ArrayList<>();
    for (String entityId : entry.entityIds()) {
        CachedEntity e = cacheStore.get(entityId, tenantId);
        if (e != null) broaderEntities.add(e);
    }
    if (broaderEntities.isEmpty()) continue;
    var subsumed = subsumptionRule.subsume(normalized, broaderEntities, broaderNormalized);
    if (subsumed.isPresent()) {
        List<CachedEntity> result = subsumed.get();
        if (researchSessionId != null) {
            result.forEach(e -> metadataStore.addSession(e.id(), researchSessionId));
        }
        return result;
    }
}
```

Update the `record()` call to pass query parameters extracted from the `NormalizedQuery`.

- [ ] **Step 8: Update existing orchestrator callers**

Update `record()` calls in the orchestrator to pass query type/parameters. Update test constructor calls to pass `SpatialSubsumptionRule`.

- [ ] **Step 9: Run full module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline`
Expected: all tests PASS

- [ ] **Step 10: Commit**

```bash
git add knowledge-pipeline/src knowledge-pipeline-api/src
git commit -m "feat(#419): wire SubsumptionRule into orchestrator search flow

Add query_type/lat/lng/radius_meters/category columns to query_cache
(V3 migration). QueryCacheStore.listForTenant() enables subsumption
scan as fallback after exact cache key miss. SpatialSubsumptionRule
filters broader cached results for narrower queries.

Closes #419

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 6: Implement refreshStale (#420)

**Files:**
- Modify: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/CachedEntity.java` (add `detailFetchedAt` field)
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/StaleEntitiesRefreshed.java`
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/CacheDecayPolicy.java` (add `StaleFieldGroup`, `staleGroups()`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestrator.java` (implement `refreshStale`)
- Modify: all `CachedEntity` construction sites (add `null` for new parameter)
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/CacheDecayPolicyTest.java` (new)
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestratorTest.java` (add refreshStale test)

**Interfaces:**
- Consumes: `SpatialCacheStore.listAll(tenantId)` (from Task 3), `LocationPlatform.placeDetails()` (existing connector SPI)
- Produces: `CachedEntity.detailFetchedAt() → Instant` (nullable), `CacheDecayPolicy.StaleFieldGroup` enum, `CacheDecayPolicy.staleGroups(entity, now) → Set<StaleFieldGroup>`, `StaleEntitiesRefreshed` CDI event

- [ ] **Step 1: Add detailFetchedAt to CachedEntity**

Update the record to add the field after `fetchedAt`:

```java
public record CachedEntity(
    String id, String name, Coordinates coordinates, String category,
    String source, String externalId, Map<String, String> properties,
    Instant fetchedAt, Instant detailFetchedAt, Instant expiresAt,
    Set<String> sessionIds, boolean hasDetail
) { ... }
```

- [ ] **Step 2: Fix all compilation errors from new CachedEntity field**

Search all `new CachedEntity(` calls with `ide_search_text`. Add `null` (or appropriate value) as the `detailFetchedAt` parameter at position 9 (between `fetchedAt` and `expiresAt`). This affects tests, InMemorySpatialCacheStore.expire(), orchestrator, and test helpers.

- [ ] **Step 3: Update SqliteSpatialCacheStore to read/write detailFetchedAt**

In `mapRow()`, read `detail_fetched_at` from ResultSet and pass to CachedEntity constructor.
In `upsertMetadata()`, write `entity.detailFetchedAt()` instead of `null` (line 240).
In `InMemorySpatialCacheStore.expire()`, preserve `detailFetchedAt` in the reconstructed entity.

- [ ] **Step 4: Write test for CacheDecayPolicy.staleGroups**

```java
// New file: CacheDecayPolicyTest.java
package io.casehub.neocortex.knowledge.cache;

import io.casehub.connectors.location.model.Coordinates;
import io.casehub.neocortex.knowledge.CachedEntity;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class CacheDecayPolicyTest {

    private final CacheDecayPolicy policy = new CacheDecayPolicy();

    private CachedEntity entityWithTimestamps(Instant fetchedAt, Instant detailFetchedAt) {
        return new CachedEntity("e1", "Place", new Coordinates(51.5, -0.1),
            "restaurant", "google", "ext-1", Map.of(),
            fetchedAt, detailFetchedAt,
            Instant.now().plusSeconds(86400), Set.of(), detailFetchedAt != null);
    }

    @Test
    void freshEntityHasNoStaleGroups() {
        Instant now = Instant.now();
        var entity = entityWithTimestamps(now, now);
        assertThat(policy.staleGroups(entity, now)).isEmpty();
    }

    @Test
    void nullDetailFetchedAtIsDetailStale() {
        Instant now = Instant.now();
        var entity = entityWithTimestamps(now, null);
        assertThat(policy.staleGroups(entity, now))
            .contains(CacheDecayPolicy.StaleFieldGroup.DETAIL);
    }

    @Test
    void oldDetailFetchedAtIsDetailStale() {
        Instant now = Instant.now();
        var entity = entityWithTimestamps(now, now.minus(Duration.ofDays(5)));
        assertThat(policy.staleGroups(entity, now))
            .contains(CacheDecayPolicy.StaleFieldGroup.DETAIL);
    }

    @Test
    void oldFetchedAtIsBasicStale() {
        Instant now = Instant.now();
        var entity = entityWithTimestamps(now.minus(Duration.ofDays(35)), now);
        assertThat(policy.staleGroups(entity, now))
            .contains(CacheDecayPolicy.StaleFieldGroup.BASIC);
    }
}
```

- [ ] **Step 5: Run test to verify it fails**

Expected: FAIL — `StaleFieldGroup` and `staleGroups()` don't exist

- [ ] **Step 6: Implement StaleFieldGroup and staleGroups**

```java
// In CacheDecayPolicy.java, add:
public enum StaleFieldGroup { BASIC, DETAIL }

public Set<StaleFieldGroup> staleGroups(CachedEntity entity, Instant now) {
    Set<StaleFieldGroup> stale = java.util.EnumSet.noneOf(StaleFieldGroup.class);
    if (entity.fetchedAt() != null
            && entity.fetchedAt().plus(coordinatesTtl).isBefore(now)) {
        stale.add(StaleFieldGroup.BASIC);
    }
    Duration detailTtl = minDuration(ratingTtl, contactTtl, hoursTtl, reviewsTtl);
    if (entity.detailFetchedAt() == null
            || entity.detailFetchedAt().plus(detailTtl).isBefore(now)) {
        stale.add(StaleFieldGroup.DETAIL);
    }
    return stale;
}

private static Duration minDuration(Duration... durations) {
    Duration min = durations[0];
    for (int i = 1; i < durations.length; i++) {
        if (durations[i].compareTo(min) < 0) min = durations[i];
    }
    return min;
}
```

- [ ] **Step 7: Run CacheDecayPolicy tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline -Dtest=CacheDecayPolicyTest`
Expected: PASS

- [ ] **Step 8: Create StaleEntitiesRefreshed event**

```java
// knowledge-pipeline-api/src/main/java/.../knowledge/StaleEntitiesRefreshed.java
package io.casehub.neocortex.knowledge;

public record StaleEntitiesRefreshed(String tenantId, int refreshedCount) {}
```

- [ ] **Step 9: Implement refreshStale in orchestrator**

Replace the placeholder with the full implementation per the spec design (section 8). Use `LocationPlatform.placeDetails()` for DETAIL refresh, skip BASIC refresh initially (safety net — can be added later when a concrete use case arises).

- [ ] **Step 10: Write and run refreshStale test**

Test that stale entities get their `detailFetchedAt` updated after refresh. Use a stub LocationPlatform that returns updated Place data.

- [ ] **Step 11: Run full module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline,knowledge-pipeline-api`
Expected: all tests PASS

- [ ] **Step 12: Commit**

```bash
git add knowledge-pipeline-api/src knowledge-pipeline/src
git commit -m "feat(#420): implement refreshStale — staleness-triggered re-fetch

Add detailFetchedAt to CachedEntity. CacheDecayPolicy.staleGroups()
classifies BASIC/DETAIL staleness. KnowledgePipelineOrchestrator
.refreshStale() scans entities, re-fetches stale details from
LocationPlatform, fires StaleEntitiesRefreshed CDI event.

Closes #420

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 4: CDI Wiring (#423)

### Task 7: Add CDI wiring — DefaultBeans, @ApplicationScoped (#423)

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineConfig.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineDefaultBeans.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/CacheEvictionTask.java`
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestrator.java` (add `@ApplicationScoped`, `@Inject`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/research/ResearchOrchestrator.java` (add `@ApplicationScoped`, `@Inject`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/promotion/EntityPromoter.java` (add `@ApplicationScoped`, `@Inject`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/SqliteSpatialCacheStore.java` (add `@ApplicationScoped`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/QueryCacheStore.java` (add `@ApplicationScoped`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/dedup/DedupIndexStore.java` (add `@ApplicationScoped`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/EntityMetadataStore.java` (add `@ApplicationScoped`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/research/ResearchSessionStore.java` (add `@ApplicationScoped`)
- Modify: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/InMemorySpatialCacheStore.java` (add `@Alternative @Priority(2)`)

**Interfaces:**
- Consumes: All classes from Tasks 1-6 in their final form
- Produces: CDI-wired knowledge pipeline ready for Quarkus deployment

- [ ] **Step 1: Create KnowledgePipelineConfig**

```java
package io.casehub.neocortex.knowledge;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

import java.time.Duration;

@ConfigMapping(prefix = "casehub.knowledge")
public interface KnowledgePipelineConfig {

    @WithDefault("5")
    int geohashPrecision();

    CacheConfig cache();
    ResearchConfig research();

    interface CacheConfig {
        @WithDefault("P90D") Duration maxEntityAge();
        @WithDefault("P1D") Duration searchResultsTtl();
        @WithDefault("P30D") Duration coordinatesTtl();
        @WithDefault("P3D") Duration ratingTtl();
        @WithDefault("P7D") Duration contactTtl();
        @WithDefault("P7D") Duration hoursTtl();
        @WithDefault("P3D") Duration reviewsTtl();
        @WithDefault("P14D") Duration imagesTtl();
        @WithDefault("24h") Duration evictionInterval();
    }

    interface ResearchConfig {
        @WithDefault("P180D") Duration maxSessionDuration();
    }
}
```

- [ ] **Step 2: Create KnowledgePipelineDefaultBeans**

```java
package io.casehub.neocortex.knowledge;

import io.casehub.neocortex.knowledge.cache.CacheDecayPolicy;
import io.casehub.neocortex.knowledge.cache.CacheEvictionScheduler;
import io.casehub.neocortex.knowledge.cache.SpatialSubsumptionRule;
import io.casehub.neocortex.knowledge.resolution.EntityResolutionEngine;
import io.casehub.neocortex.knowledge.resolution.PlaceMatcher;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;

@ApplicationScoped
public class KnowledgePipelineDefaultBeans {

    @Produces @DefaultBean
    CacheDecayPolicy cacheDecayPolicy(KnowledgePipelineConfig config) {
        var c = config.cache();
        return new CacheDecayPolicy(c.coordinatesTtl(), c.ratingTtl(),
            c.contactTtl(), c.hoursTtl(), c.reviewsTtl(), c.imagesTtl(),
            c.searchResultsTtl());
    }

    @Produces @DefaultBean
    SubsumptionRule subsumptionRule() {
        return new SpatialSubsumptionRule();
    }

    @Produces @DefaultBean
    EntityMatcher entityMatcher() {
        return new PlaceMatcher();
    }

    @Produces @DefaultBean
    EntityResolutionEngine entityResolutionEngine(EntityMatcher matcher) {
        return new EntityResolutionEngine(matcher);
    }
}
```

- [ ] **Step 3: Create CacheEvictionTask**

```java
package io.casehub.neocortex.knowledge;

import io.casehub.neocortex.knowledge.cache.CacheEvictionScheduler;
import io.quarkus.scheduler.Scheduled;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class CacheEvictionTask {

    @Inject
    CacheEvictionScheduler scheduler;

    @Scheduled(every = "${casehub.knowledge.cache.eviction-interval:24h}")
    void runEviction() {
        scheduler.runEviction();
    }
}
```

- [ ] **Step 4: Add CDI annotations to all service classes**

Add `@ApplicationScoped` and `@Inject` to constructors of:
- `KnowledgePipelineOrchestrator` — change `List<LocationPlatform>` to `Instance<LocationPlatform>`
- `ResearchOrchestrator`
- `EntityPromoter`
- `CacheEvictionScheduler`

Add `@ApplicationScoped` to store classes:
- `SqliteSpatialCacheStore`
- `QueryCacheStore`
- `DedupIndexStore`
- `EntityMetadataStore`
- `ResearchSessionStore`

Add `@Alternative @Priority(2)` to `InMemorySpatialCacheStore`.

- [ ] **Step 5: Add SqliteDataSourceFactory wiring for stores**

Use `SqliteDataSourceFactory` with config key `casehub.knowledge.sqlite.path` to produce the shared `HikariDataSource` for all SQLite stores. Add a `@Produces @DefaultBean @ApplicationScoped` method in `KnowledgePipelineDefaultBeans`:

```java
@Produces @DefaultBean @ApplicationScoped
HikariDataSource knowledgeDataSource(
        @ConfigProperty(name = "casehub.knowledge.sqlite.path",
                        defaultValue = "knowledge-pipeline.db") String path) {
    return SqliteDataSourceFactory.create(path, "db/knowledge-pipeline", "db/knowledge-research");
}
```

- [ ] **Step 6: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl knowledge-pipeline`
Expected: compilation succeeds

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl knowledge-pipeline`
Expected: all tests PASS (tests use direct construction, not CDI — CDI annotations are additive)

- [ ] **Step 8: Commit**

```bash
git add knowledge-pipeline/src knowledge-pipeline-api/src
git commit -m "feat(#423): add CDI wiring for knowledge-pipeline

KnowledgePipelineConfig @ConfigMapping, KnowledgePipelineDefaultBeans
producer class, @ApplicationScoped on all services and stores,
@Alternative @Priority(2) on InMemorySpatialCacheStore,
CacheEvictionTask @Scheduled for periodic eviction.

Closes #423

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## References

- [2026-10-04-knowledge-pipeline-phase-2-design.md] — design spec this plan implements
- `knowledge-pipeline/KnowledgePipelineOrchestrator.java` — search flow, refreshStale stub
- `knowledge-pipeline/cache/QueryCacheStore.java` — exact key lookup, schema
- `knowledge-pipeline/cache/CacheEvictionScheduler.java` — eviction loop
- `knowledge-pipeline/cache/CacheDecayPolicy.java` — per-field TTLs
- `knowledge-pipeline/cache/SpatialSubsumptionRule.java` — subsumption SPI impl
- `knowledge-pipeline/cache/SqliteSpatialCacheStore.java` — SQLite spatial store
- `knowledge-pipeline/cache/InMemorySpatialCacheStore.java` — in-memory test store
- `knowledge-pipeline/cache/EntityMetadataStore.java` — entity metadata + sessions
- `knowledge-pipeline/research/ResearchOrchestrator.java` — session lifecycle
- `knowledge-pipeline/promotion/EntityPromoter.java` — ensureSubgraph copy
- `knowledge-pipeline-api/CachedEntity.java` — entity record (11 → 12 fields)
- `knowledge-pipeline-api/SpatialCacheStore.java` — SPI (7 → 8 methods)
- `mindmap-intelligence/CheckInService.java` — ensureSubgraph copy
- `mindmap-intelligence/consolidation/ExperienceConsolidationPhase.java` — 2 ensureSubgraph copies
- `mindmap-intelligence/ConversationBridge.java` — ensureSubgraph copy
- `db/knowledge-pipeline/V1__init.sql` — initial schema (detail_fetched_at already present)
- `db/knowledge-pipeline/V2__spatial_cache.sql` — spatial index migration
- GitHub #418, #419, #420, #421, #422, #423, #426, #427
