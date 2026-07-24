# Scope Erasure + Aggregate Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #158 — scope-based bulk erasure
**Issue group:** #158, #159

**Goal:** Add `eraseByScope(Path, tenantId)` to the CBR SPI with subtree
semantics, implement in all backends, and fire `CbrCasesErased` CDI events
on all explicit erasure operations.

**Architecture:** `eraseByScope` is an abstract SPI method on
`CbrCaseMemoryStore` + `ReactiveCbrCaseMemoryStore`. Subtree semantics:
`scope.equals(stored) || scope.isAncestorOf(stored)`. `CbrCasesErased` is
a sealed interface with `ByRequest`, `ByEntity`, `ByScope` subtypes, fired
by a blocking-only decorator at `@Priority(45)`.

**Tech Stack:** Java 21, Quarkus CDI, Qdrant gRPC client, JPA/Hibernate,
platform `Path` (io.casehub.platform.api.path.Path)

## Global Constraints

- Java 21 language level, Java 26 JVM
- Pre-release: breaking changes are free
- Abstract method (not default) — all implementations in this repo
- Subtree semantics: scope + all descendants; root erases all for tenant
- CDI `Event.fire()` (synchronous) for blocking notification decorator — matches TrackingCbrCaseMemoryStore pattern
- Blocking-only notification decorator — no reactive counterpart (BlockingToReactiveCbrBridge routes all reactive calls through blocking chain)
- No SPI-level authorization — auth belongs at the API boundary
- IntelliJ MCP mandatory for all source file operations

---

### Task 1: SPI + CbrCasesErased + InMemory + all forwarding + contract tests

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrCaseMemoryStore.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCasesErased.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingToReactiveCbrBridge.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TemporalDecayCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveTemporalDecayCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/OutcomeWeightingCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveOutcomeWeightingCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ScopeDecayCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveScopeDecayCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TrendEnrichmentCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveTrendEnrichmentCbrCaseMemoryStore.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/ReactiveRerankingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/ReactiveTrackingCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Produces: `CbrCaseMemoryStore.eraseByScope(Path, String)` → `Integer`,
  `ReactiveCbrCaseMemoryStore.eraseByScope(Path, String)` → `Uni<Integer>`,
  `CbrCasesErased` sealed interface with `ByRequest`, `ByEntity`, `ByScope` subtypes
- Consumes: `io.casehub.platform.api.path.Path` (isAncestorOf, root, of, depth, value)

- [ ] **Step 1: Add eraseByScope to CbrCaseMemoryStore**

Add as default method (temporary — Task 3 makes it abstract once all backends implement):

```java
default Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    throw new UnsupportedOperationException("eraseByScope not yet implemented");
}
```

Use `ide_insert_member` on `CbrCaseMemoryStore`, position `after` anchor `eraseEntity`.

- [ ] **Step 2: Add eraseByScope to ReactiveCbrCaseMemoryStore**

```java
default Uni<Integer> eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    return Uni.createFrom().failure(new UnsupportedOperationException("eraseByScope not yet implemented"));
}
```

Use `ide_insert_member` on `ReactiveCbrCaseMemoryStore`, position `after` anchor `eraseEntity`.

- [ ] **Step 3: Create CbrCasesErased sealed interface**

Use `ide_create_file`:

```java
package io.casehub.neocortex.memory.cbr;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.platform.api.path.Path;

import java.time.Instant;
import java.util.Objects;

public sealed interface CbrCasesErased {
    String tenantId();
    int erasedCount();
    Instant erasedAt();

    record ByRequest(String tenantId, int erasedCount,
                     String entityId, MemoryDomain domain, String caseId,
                     Instant erasedAt) implements CbrCasesErased {
        public ByRequest {
            Objects.requireNonNull(tenantId, "tenantId");
            Objects.requireNonNull(entityId, "entityId");
            Objects.requireNonNull(domain, "domain");
            Objects.requireNonNull(erasedAt, "erasedAt");
        }
    }

    record ByEntity(String tenantId, int erasedCount,
                    String entityId,
                    Instant erasedAt) implements CbrCasesErased {
        public ByEntity {
            Objects.requireNonNull(tenantId, "tenantId");
            Objects.requireNonNull(entityId, "entityId");
            Objects.requireNonNull(erasedAt, "erasedAt");
        }
    }

    record ByScope(String tenantId, int erasedCount,
                   Path scope,
                   Instant erasedAt) implements CbrCasesErased {
        public ByScope {
            Objects.requireNonNull(tenantId, "tenantId");
            Objects.requireNonNull(scope, "scope");
            Objects.requireNonNull(erasedAt, "erasedAt");
        }
    }
}
```

- [ ] **Step 4: Write contract tests for eraseByScope**

Add 8 tests to `CbrCaseMemoryStoreContractTest`. Use `ide_insert_member` with
position `before` anchor `scope_roundTrip_scopePreservedOnScoredCase` to keep
scope tests grouped.

```java
@Test
void eraseByScope_exactScope_erasesOnlyCasesAtThatScope() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("at-target", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase", ENTITY, CBR, TENANT, "c-1", Path.of("org", "site"));
    store().store(new FeatureVectorCbrCase("at-parent", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase", ENTITY, CBR, TENANT, "c-2", Path.of("org"));
    int erased = store().eraseByScope(Path.of("org", "site"), TENANT);
    assertThat(erased).isEqualTo(1);
    var q = CbrQuery.of(TENANT, CBR, Path.of("org"), "scoped-erase",
                        Map.of("level", string("a")), 10);
    assertThat(store().retrieveSimilar(q, FeatureVectorCbrCase.class)).hasSize(1);
}

@Test
void eraseByScope_parentScope_erasesAllDescendants() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase2",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("at-parent", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase2", ENTITY, CBR, TENANT, "c-1", Path.of("org"));
    store().store(new FeatureVectorCbrCase("at-child", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase2", ENTITY, CBR, TENANT, "c-2", Path.of("org", "site"));
    store().store(new FeatureVectorCbrCase("at-grandchild", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase2", ENTITY, CBR, TENANT, "c-3", Path.of("org", "site", "ward"));
    int erased = store().eraseByScope(Path.of("org"), TENANT);
    assertThat(erased).isEqualTo(3);
}

@Test
void eraseByScope_rootScope_erasesAllCasesForTenant() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase3",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("root-case", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase3", ENTITY, CBR, TENANT, "c-1", Path.root());
    store().store(new FeatureVectorCbrCase("nested-case", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase3", ENTITY, CBR, TENANT, "c-2", Path.of("org", "site"));
    int erased = store().eraseByScope(Path.root(), TENANT);
    assertThat(erased).isEqualTo(2);
}

@Test
void eraseByScope_tenantIsolation() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase4",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("t1-case", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase4", ENTITY, CBR, TENANT, "c-1", Path.of("org"));
    store().store(new FeatureVectorCbrCase("t2-case", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase4", ENTITY, CBR, "other-tenant", "c-2", Path.of("org"));
    int erased = store().eraseByScope(Path.of("org"), TENANT);
    assertThat(erased).isEqualTo(1);
    var q = CbrQuery.of("other-tenant", CBR, Path.of("org"), "scoped-erase4",
                        Map.of("level", string("a")), 10);
    assertThat(store().retrieveSimilar(q, FeatureVectorCbrCase.class)).hasSize(1);
}

@Test
void eraseByScope_returnsCorrectCount() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase5",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("c1", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase5", ENTITY, CBR, TENANT, "c-1", Path.of("org"));
    store().store(new FeatureVectorCbrCase("c2", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase5", ENTITY, CBR, TENANT, "c-2", Path.of("org", "site"));
    int erased = store().eraseByScope(Path.of("org"), TENANT);
    assertThat(erased).isEqualTo(2);
}

@Test
void eraseByScope_noMatchingCases_returnsZero() {
    int erased = store().eraseByScope(Path.of("nonexistent"), TENANT);
    assertThat(erased).isEqualTo(0);
}

@Test
void eraseByScope_siblingIsolation_doesNotAffectSiblingScope() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase7",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("site-a", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase7", ENTITY, CBR, TENANT, "c-1", Path.of("site-a"));
    store().store(new FeatureVectorCbrCase("site-ab", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase7", ENTITY, CBR, TENANT, "c-2", Path.of("site-ab"));
    int erased = store().eraseByScope(Path.of("site-a"), TENANT);
    assertThat(erased).isEqualTo(1);
    var q = CbrQuery.of(TENANT, CBR, Path.of("site-ab"), "scoped-erase7",
                        Map.of("level", string("a")), 10);
    assertThat(store().retrieveSimilar(q, FeatureVectorCbrCase.class)).hasSize(1);
}

@Test
void eraseByScope_supersededCasesAlsoErased() {
    store().registerSchema(CbrFeatureSchema.of("scoped-erase8",
                                               FeatureField.categorical("level")));
    store().store(new FeatureVectorCbrCase("original", "s", null, null,
                                           Map.of("level", string("a"))),
                  "scoped-erase8", ENTITY, CBR, TENANT, "c-1", Path.of("org"));
    store().supersede("c-1", TENANT, "c-2", "better case available");
    int erased = store().eraseByScope(Path.of("org"), TENANT);
    assertThat(erased).isEqualTo(1);
}
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-testing -am -Dtest=InMemoryCbrCaseMemoryStoreTest -DfailIfNoTests=false`
Expected: FAIL (8 test failures — eraseByScope throws UnsupportedOperationException)

- [ ] **Step 6: Implement eraseByScope in InMemoryCbrCaseMemoryStore**

Use `ide_insert_member` position `after` anchor `eraseEntity`:

```java
@Override
public Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    java.util.Objects.requireNonNull(scope, "scope required");
    java.util.Objects.requireNonNull(tenantId, "tenantId required");
    int before = cases.size();
    cases.removeIf(sc -> sc.tenantId().equals(tenantId)
                         && (sc.scope().equals(scope) || scope.isAncestorOf(sc.scope())));
    return before - cases.size();
}
```

- [ ] **Step 7: Implement in NoOpCbrCaseMemoryStore**

Use `ide_insert_member` position `after` anchor `eraseEntity`:

```java
@Override
public Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    return 0;
}
```

- [ ] **Step 8: Forward in BlockingToReactiveCbrBridge**

Use `ide_insert_member` position `after` anchor `eraseEntity`:

```java
@Override
public Uni<Integer> eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    return Uni.createFrom().item(() -> delegate.eraseByScope(scope, tenantId))
              .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}
```

- [ ] **Step 9: Forward in all blocking decorators**

For each of these 6 files, use `ide_insert_member` position `after` anchor `eraseEntity`:

1. `TemporalDecayCbrCaseMemoryStore`: `@Override public Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) { return delegate.eraseByScope(scope, tenantId); }`
2. `OutcomeWeightingCbrCaseMemoryStore`: same pattern
3. `ScopeDecayCbrCaseMemoryStore`: same pattern
4. `TrendEnrichmentCbrCaseMemoryStore`: same pattern
5. `RerankingCbrCaseMemoryStore`: same pattern
6. `TrackingCbrCaseMemoryStore`: same pattern

- [ ] **Step 10: Forward in all reactive decorators**

For each of these 6 files, use `ide_insert_member` position `after` anchor `eraseEntity`:

1. `ReactiveTemporalDecayCbrCaseMemoryStore`: `@Override public Uni<Integer> eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) { return delegate.eraseByScope(scope, tenantId); }`
2. `ReactiveOutcomeWeightingCbrCaseMemoryStore`: same pattern
3. `ReactiveScopeDecayCbrCaseMemoryStore`: same pattern
4. `ReactiveTrendEnrichmentCbrCaseMemoryStore`: same pattern
5. `ReactiveRerankingCbrCaseMemoryStore`: same pattern
6. `ReactiveTrackingCbrCaseMemoryStore`: same pattern

- [ ] **Step 11: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -am`
Expected: PASS — all 8 new eraseByScope tests plus existing 134 tests green.

- [ ] **Step 12: Commit**

```
feat(#158): eraseByScope SPI + InMemory + contract tests + forwarding

Adds eraseByScope(Path, String) to CbrCaseMemoryStore and
ReactiveCbrCaseMemoryStore with subtree semantics. Implements in
InMemory backend. Creates CbrCasesErased sealed interface for #159.
All decorators and bridge forward the new method.
```

---

### Task 2: JPA eraseByScope implementation

**Files:**
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore.eraseByScope(Path, String)` from Task 1
- Produces: JPA-backed implementation using existing `scope` column

- [ ] **Step 1: Override eraseByScope in JpaCbrCaseMemoryStore**

Use `ide_insert_member` position `after` anchor `eraseEntity`:

```java
@Override
@Transactional
public Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    java.util.Objects.requireNonNull(scope, "scope required");
    java.util.Objects.requireNonNull(tenantId, "tenantId required");
    if (scope.segments().isEmpty()) {
        return em.createQuery("DELETE FROM CbrCaseEntity e WHERE e.tenantId = :t")
                 .setParameter("t", tenantId)
                 .executeUpdate();
    }
    return em.createQuery("DELETE FROM CbrCaseEntity e WHERE e.tenantId = :t AND (e.scope = :s OR e.scope LIKE :prefix)")
             .setParameter("t", tenantId)
             .setParameter("s", scope.value())
             .setParameter("prefix", scope.value() + "/%")
             .executeUpdate();
}
```

- [ ] **Step 2: Run JPA module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-jpa -am`
Expected: PASS — contract tests pass with JPA backend.

- [ ] **Step 3: Commit**

```
feat(#158): JPA eraseByScope — DELETE with scope prefix matching
```

---

### Task 3: Qdrant eraseByScope + make SPI abstract

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore.eraseByScope(Path, String)` from Task 1,
  `CbrCollectionManager` (collectionName, client, deleteByFilter),
  `CaseMemoryStore.erase(EraseRequest)` (nullable delegate)
- Produces: Qdrant scroll+delete implementation

- [ ] **Step 1: Implement eraseByScope in QdrantCbrCaseMemoryStore**

Use `ide_insert_member` position `after` anchor `eraseEntity`. The implementation scrolls with
tenantId filter, checks scope client-side, deletes matching points, and delegates per-case
to `CaseMemoryStore` using `EraseRequest` with `caseId` from the scroll results.

```java
@Override
public Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
    java.util.Objects.requireNonNull(scope, "scope required");
    java.util.Objects.requireNonNull(tenantId, "tenantId required");

    int totalErased = 0;
    for (String caseType : schemas.keySet()) {
        String collection = collectionManager.collectionName(caseType);
        try {
            if (!collectionManager.client().collectionExistsAsync(collection).get()) {
                continue;
            }

            Filter tenantFilter = Filter.newBuilder()
                                        .addMust(ConditionFactory.matchKeyword("tenantId", tenantId))
                                        .build();

            List<String> pointIdsToDelete = new java.util.ArrayList<>();
            io.qdrant.client.grpc.Points.PointId lastId = null;
            boolean hasMore = true;

            while (hasMore) {
                var scrollBuilder = io.qdrant.client.grpc.Points.ScrollPoints.newBuilder()
                                                                             .setCollectionName(collection)
                                                                             .setFilter(tenantFilter)
                                                                             .setLimit(100)
                                                                             .setWithPayload(io.qdrant.client.WithPayloadSelectorFactory.enable());
                if (lastId != null) {
                    scrollBuilder.setOffset(lastId);
                }

                var response = collectionManager.client().scrollAsync(scrollBuilder.build()).get();
                var points = response.getResultList();

                for (var point : points) {
                    Map<String, Value> payload = point.getPayloadMap();
                    io.casehub.platform.api.path.Path storedScope = extractScope(payload);
                    if (scope.segments().isEmpty() || storedScope.equals(scope)
                        || scope.isAncestorOf(storedScope)) {
                        pointIdsToDelete.add(point.getId().getUuid());
                        if (delegate != null) {
                            String entityId = extractString(payload, "entityId");
                            String domain = extractString(payload, "domain");
                            String caseId = extractString(payload, "caseId");
                            if (entityId != null && domain != null && caseId != null) {
                                delegate.erase(new EraseRequest(entityId,
                                                                new MemoryDomain(domain), tenantId, caseId));
                            }
                        }
                    }
                }

                hasMore = points.size() == 100;
                if (!points.isEmpty()) {
                    lastId = points.get(points.size() - 1).getId();
                }
            }

            if (!pointIdsToDelete.isEmpty()) {
                var selector = io.qdrant.client.grpc.Points.PointsSelector.newBuilder()
                                                                          .setPoints(io.qdrant.client.grpc.Points.PointsIdsList.newBuilder()
                                                                                                                               .addAllIds(pointIdsToDelete.stream()
                                                                                                                                                          .map(id -> io.qdrant.client.grpc.Points.PointId.newBuilder().setUuid(id).build())
                                                                                                                                                          .toList()))
                                                                          .build();
                collectionManager.client().deleteAsync(collection, selector).get();
                totalErased += pointIdsToDelete.size();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted during eraseByScope", e);
        } catch (java.util.concurrent.ExecutionException e) {
            throw new RuntimeException("eraseByScope failed", e.getCause());
        }
    }
    return totalErased;
}
```

- [ ] **Step 2: Remove default from CbrCaseMemoryStore.eraseByScope**

Use `ide_edit_member` to replace the default method with an abstract declaration:

```java
Integer eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId);
```

- [ ] **Step 3: Remove default from ReactiveCbrCaseMemoryStore.eraseByScope**

Use `ide_edit_member` to replace the default method with an abstract declaration:

```java
Uni<Integer> eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId);
```

- [ ] **Step 4: Build full project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: PASS — all modules compile with abstract method.

- [ ] **Step 5: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem,memory-cbr-jpa -am`
Expected: PASS — all contract tests green across both backends.

- [ ] **Step 6: Commit**

```
feat(#158): Qdrant eraseByScope — scroll+delete with CaseMemoryStore delegation

Makes eraseByScope abstract on both SPIs now that all backends implement it.
```

---

### Task 4: ErasureNotificationCbrCaseMemoryStore + tests

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ErasureNotificationCbrCaseMemoryStore.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/ErasureNotificationCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore` (delegate), `CbrCasesErased.ByRequest`, `CbrCasesErased.ByEntity`,
  `CbrCasesErased.ByScope` (CDI Event injection), `EraseRequest`, `Path`
- Produces: CDI events fired on erase/eraseEntity/eraseByScope when count > 0

- [ ] **Step 1: Write failing test**

Create `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/ErasureNotificationCbrCaseMemoryStoreTest.java`:

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.CbrCase;
import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.cbr.CbrCasesErased;
import io.casehub.neocortex.memory.cbr.CbrFeatureSchema;
import io.casehub.neocortex.memory.cbr.CbrOutcome;
import io.casehub.neocortex.memory.cbr.CbrQuery;
import io.casehub.neocortex.memory.cbr.CbrRetentionPolicy;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import io.casehub.platform.api.path.Path;
import jakarta.enterprise.event.Event;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ErasureNotificationCbrCaseMemoryStoreTest {

    private static final Instant FIXED = Instant.parse("2026-07-17T12:00:00Z");
    private static final Clock CLOCK = Clock.fixed(FIXED, ZoneOffset.UTC);
    private static final MemoryDomain CBR = new MemoryDomain("cbr");

    private StubStore stub;
    private List<CbrCasesErased.ByRequest> byRequestEvents;
    private List<CbrCasesErased.ByEntity> byEntityEvents;
    private List<CbrCasesErased.ByScope> byScopeEvents;
    private ErasureNotificationCbrCaseMemoryStore decorator;

    @BeforeEach
    void setUp() {
        stub = new StubStore();
        byRequestEvents = new ArrayList<>();
        byEntityEvents = new ArrayList<>();
        byScopeEvents = new ArrayList<>();
        decorator = new ErasureNotificationCbrCaseMemoryStore(
                stub,
                capturingEvent(byRequestEvents),
                capturingEvent(byEntityEvents),
                capturingEvent(byScopeEvents),
                CLOCK);
    }

    @Test
    void erase_firesEvent_whenCountPositive() {
        stub.eraseReturnValue = 3;
        var request = new EraseRequest("e-1", CBR, "t-1", "c-1");
        int result = decorator.erase(request);
        assertThat(result).isEqualTo(3);
        assertThat(byRequestEvents).hasSize(1);
        var event = byRequestEvents.getFirst();
        assertThat(event.tenantId()).isEqualTo("t-1");
        assertThat(event.erasedCount()).isEqualTo(3);
        assertThat(event.entityId()).isEqualTo("e-1");
        assertThat(event.domain()).isEqualTo(CBR);
        assertThat(event.caseId()).isEqualTo("c-1");
        assertThat(event.erasedAt()).isEqualTo(FIXED);
    }

    @Test
    void erase_noEvent_whenCountZero() {
        stub.eraseReturnValue = 0;
        decorator.erase(new EraseRequest("e-1", CBR, "t-1", null));
        assertThat(byRequestEvents).isEmpty();
    }

    @Test
    void eraseEntity_firesEvent_whenCountPositive() {
        stub.eraseEntityReturnValue = 5;
        int result = decorator.eraseEntity("e-1", "t-1");
        assertThat(result).isEqualTo(5);
        assertThat(byEntityEvents).hasSize(1);
        var event = byEntityEvents.getFirst();
        assertThat(event.tenantId()).isEqualTo("t-1");
        assertThat(event.erasedCount()).isEqualTo(5);
        assertThat(event.entityId()).isEqualTo("e-1");
        assertThat(event.erasedAt()).isEqualTo(FIXED);
    }

    @Test
    void eraseEntity_noEvent_whenCountZero() {
        stub.eraseEntityReturnValue = 0;
        decorator.eraseEntity("e-1", "t-1");
        assertThat(byEntityEvents).isEmpty();
    }

    @Test
    void eraseByScope_firesEvent_whenCountPositive() {
        stub.eraseByScopeReturnValue = 7;
        int result = decorator.eraseByScope(Path.of("org", "site"), "t-1");
        assertThat(result).isEqualTo(7);
        assertThat(byScopeEvents).hasSize(1);
        var event = byScopeEvents.getFirst();
        assertThat(event.tenantId()).isEqualTo("t-1");
        assertThat(event.erasedCount()).isEqualTo(7);
        assertThat(event.scope()).isEqualTo(Path.of("org", "site"));
        assertThat(event.erasedAt()).isEqualTo(FIXED);
    }

    @Test
    void eraseByScope_noEvent_whenCountZero() {
        stub.eraseByScopeReturnValue = 0;
        decorator.eraseByScope(Path.of("org"), "t-1");
        assertThat(byScopeEvents).isEmpty();
    }

    @Test
    void purge_doesNotFireEvent() {
        stub.purgeReturnValue = 10;
        decorator.purge(new CbrRetentionPolicy("t-1", CBR, null, 30, null));
        assertThat(byRequestEvents).isEmpty();
        assertThat(byEntityEvents).isEmpty();
        assertThat(byScopeEvents).isEmpty();
    }

    @SuppressWarnings("unchecked")
    private static <T> Event<T> capturingEvent(List<T> captured) {
        return new Event<>() {
            @Override public void fire(T event) { captured.add(event); }
            @Override public <U extends T> jakarta.enterprise.event.Event<U> select(Class<U> subtype, java.lang.annotation.Annotation... qualifiers) { throw new UnsupportedOperationException(); }
            @Override public <U extends T> jakarta.enterprise.event.Event<U> select(java.lang.annotation.Annotation... qualifiers) { throw new UnsupportedOperationException(); }
            @Override public <U extends T> jakarta.enterprise.event.Event<U> select(jakarta.enterprise.util.TypeLiteral<U> subtype, java.lang.annotation.Annotation... qualifiers) { throw new UnsupportedOperationException(); }
            @Override public java.util.concurrent.CompletionStage<U> fireAsync(Object event) { throw new UnsupportedOperationException(); }
            @Override public java.util.concurrent.CompletionStage<U> fireAsync(Object event, jakarta.enterprise.event.NotificationOptions options) { throw new UnsupportedOperationException(); }
        };
    }

    private static class StubStore implements CbrCaseMemoryStore {
        int eraseReturnValue = 0;
        int eraseEntityReturnValue = 0;
        int eraseByScopeReturnValue = 0;
        int purgeReturnValue = 0;

        @Override public void registerSchema(CbrFeatureSchema schema) {}
        @Override public String store(CbrCase c, String ct, String e, MemoryDomain d, String t, String ci, Path scope) { return ""; }
        @Override public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery q, Class<C> ct) { return List.of(); }
        @Override public Integer erase(EraseRequest request) { return eraseReturnValue; }
        @Override public Integer eraseEntity(String entityId, String tenantId) { return eraseEntityReturnValue; }
        @Override public Integer eraseByScope(Path scope, String tenantId) { return eraseByScopeReturnValue; }
        @Override public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {}
        @Override public Integer purge(CbrRetentionPolicy policy) { return purgeReturnValue; }
        @Override public void supersede(String caseId, String tenantId, String supersedingCaseId, String reason) {}
        @Override public void reinstate(String caseId, String tenantId) {}
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=ErasureNotificationCbrCaseMemoryStoreTest`
Expected: FAIL — `ErasureNotificationCbrCaseMemoryStore` class not found.

- [ ] **Step 3: Create ErasureNotificationCbrCaseMemoryStore**

Use `ide_create_file`:

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.CbrCase;
import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.cbr.CbrCasesErased;
import io.casehub.neocortex.memory.cbr.CbrFeatureSchema;
import io.casehub.neocortex.memory.cbr.CbrOutcome;
import io.casehub.neocortex.memory.cbr.CbrQuery;
import io.casehub.neocortex.memory.cbr.CbrRetentionPolicy;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import io.casehub.platform.api.path.Path;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.time.Clock;
import java.time.Instant;
import java.util.List;

@Decorator
@Priority(45)
public class ErasureNotificationCbrCaseMemoryStore implements CbrCaseMemoryStore {

    private final CbrCaseMemoryStore delegate;
    private final Event<CbrCasesErased.ByRequest> byRequestEvent;
    private final Event<CbrCasesErased.ByEntity> byEntityEvent;
    private final Event<CbrCasesErased.ByScope> byScopeEvent;
    private final Clock clock;

    @Inject
    public ErasureNotificationCbrCaseMemoryStore(
            @Delegate @Any CbrCaseMemoryStore delegate,
            Event<CbrCasesErased.ByRequest> byRequestEvent,
            Event<CbrCasesErased.ByEntity> byEntityEvent,
            Event<CbrCasesErased.ByScope> byScopeEvent) {
        this(delegate, byRequestEvent, byEntityEvent, byScopeEvent, Clock.systemUTC());
    }

    ErasureNotificationCbrCaseMemoryStore(
            CbrCaseMemoryStore delegate,
            Event<CbrCasesErased.ByRequest> byRequestEvent,
            Event<CbrCasesErased.ByEntity> byEntityEvent,
            Event<CbrCasesErased.ByScope> byScopeEvent,
            Clock clock) {
        this.delegate = delegate;
        this.byRequestEvent = byRequestEvent;
        this.byEntityEvent = byEntityEvent;
        this.byScopeEvent = byScopeEvent;
        this.clock = clock;
    }

    @Override
    public Integer erase(EraseRequest request) {
        int count = delegate.erase(request);
        if (count > 0) {
            byRequestEvent.fire(new CbrCasesErased.ByRequest(
                    request.tenantId(), count, request.entityId(),
                    request.domain(), request.caseId(),
                    Instant.now(clock)));
        }
        return count;
    }

    @Override
    public Integer eraseEntity(String entityId, String tenantId) {
        int count = delegate.eraseEntity(entityId, tenantId);
        if (count > 0) {
            byEntityEvent.fire(new CbrCasesErased.ByEntity(
                    tenantId, count, entityId, Instant.now(clock)));
        }
        return count;
    }

    @Override
    public Integer eraseByScope(Path scope, String tenantId) {
        int count = delegate.eraseByScope(scope, tenantId);
        if (count > 0) {
            byScopeEvent.fire(new CbrCasesErased.ByScope(
                    tenantId, count, scope, Instant.now(clock)));
        }
        return count;
    }

    @Override public void registerSchema(CbrFeatureSchema schema) { delegate.registerSchema(schema); }
    @Override public String store(CbrCase c, String ct, String e, MemoryDomain d, String t, String ci, Path scope) { return delegate.store(c, ct, e, d, t, ci, scope); }
    @Override public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery q, Class<C> ct) { return delegate.retrieveSimilar(q, ct); }
    @Override public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) { delegate.recordOutcome(caseId, tenantId, outcome); }
    @Override public Integer purge(CbrRetentionPolicy policy) { return delegate.purge(policy); }
    @Override public void supersede(String caseId, String tenantId, String supersedingCaseId, String reason) { delegate.supersede(caseId, tenantId, supersedingCaseId, reason); }
    @Override public void reinstate(String caseId, String tenantId) { delegate.reinstate(caseId, tenantId); }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=ErasureNotificationCbrCaseMemoryStoreTest`
Expected: PASS — all 8 notification tests green.

- [ ] **Step 5: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: PASS — all modules compile and all tests green.

- [ ] **Step 6: Commit**

```
feat(#159): CbrCasesErased notification decorator — fires CDI events on erasure

ErasureNotificationCbrCaseMemoryStore @Decorator @Priority(45) fires
CbrCasesErased.ByRequest/ByEntity/ByScope events on erase, eraseEntity,
eraseByScope when count > 0. Blocking-only — no reactive counterpart
needed since BlockingToReactiveCbrBridge routes all reactive calls
through the blocking chain.
```
