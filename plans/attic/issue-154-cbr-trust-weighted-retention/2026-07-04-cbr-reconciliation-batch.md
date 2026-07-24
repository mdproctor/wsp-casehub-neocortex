# CBR Reconciliation Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use hortora:subagent-driven-development (recommended) or hortora:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CaseMemoryStore scan capability, CBR reconciliation service, dimension migration gate, and minor findings fixes (#74, #78, #79).

**Architecture:** Fix the root CaseMemoryStore enumeration gap with `MemoryCapability.SCAN` and `scan(MemoryScanRequest)` default method. Build `CbrReconciliationService` in memory-qdrant using a unified single-pass set-intersection algorithm. Gate destructive dimension migration behind config. Fix score validation and effectiveDim duplication.

**Tech Stack:** Java 21, Quarkus 3.32, Qdrant gRPC client, PostgreSQL jsonb, SQLite json_extract, JUnit 5, Testcontainers, AssertJ

## Global Constraints

- Java 21 language level, Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Build tool: `mvn` (not `./mvnw`)
- All SPI types in memory-api must be pure Java (Tier 1) — no JPA, no Quarkus runtime types
- Mutiny (`provided` scope) is acceptable in memory-api
- Every CaseMemoryStore method calls `MemoryPermissions.assertTenant()` before executing
- Qdrant operations use `io.qdrant:client` directly — not LangChain4j EmbeddingStore
- Tests: JUnit 5 + AssertJ. Qdrant integration tests use Testcontainers (`qdrant/qdrant:v1.18.0`)
- Commits reference issues: `feat(#74):`, `fix(#78):`, `fix(#79):`

---

### Task 1: ScoredCbrCase score validation and Javadoc (#79)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrCaseTest.java` (add score tests)

**Interfaces:**
- Consumes: nothing
- Produces: `ScoredCbrCase<C>(C cbrCase, double score)` — now validates `score` in `[-1, 1]`, rejects NaN/Infinity

- [ ] **Step 1: Write the failing tests**

Add to `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrCaseTest.java`:

```java
@Test
void scoredCbrCase_rejectsScoreAboveOne() {
    var c = new TextualCbrCase("p", "s", null, null);
    assertThatThrownBy(() -> new ScoredCbrCase<>(c, 1.1))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("[-1,1]");
}

@Test
void scoredCbrCase_rejectsScoreBelowNegativeOne() {
    var c = new TextualCbrCase("p", "s", null, null);
    assertThatThrownBy(() -> new ScoredCbrCase<>(c, -1.1))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("[-1,1]");
}

@Test
void scoredCbrCase_rejectsNaN() {
    var c = new TextualCbrCase("p", "s", null, null);
    assertThatThrownBy(() -> new ScoredCbrCase<>(c, Double.NaN))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void scoredCbrCase_rejectsPositiveInfinity() {
    var c = new TextualCbrCase("p", "s", null, null);
    assertThatThrownBy(() -> new ScoredCbrCase<>(c, Double.POSITIVE_INFINITY))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void scoredCbrCase_acceptsBoundaryValues() {
    var c = new TextualCbrCase("p", "s", null, null);
    assertThatCode(() -> new ScoredCbrCase<>(c, 1.0)).doesNotThrowAnyException();
    assertThatCode(() -> new ScoredCbrCase<>(c, -1.0)).doesNotThrowAnyException();
    assertThatCode(() -> new ScoredCbrCase<>(c, 0.0)).doesNotThrowAnyException();
    assertThatCode(() -> new ScoredCbrCase<>(c, 0.75)).doesNotThrowAnyException();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="CbrCaseTest#scoredCbrCase*" -DfailIfNoTests=false`
Expected: FAIL — score validation does not exist yet.

- [ ] **Step 3: Implement the validation**

Replace `ScoredCbrCase.java` compact constructor:

```java
/**
 * @param cbrCase the matched case
 * @param score similarity score in [-1, 1] — 1.0 for filter-only matches,
 *              cosine similarity for dense vector search results
 */
public ScoredCbrCase {
    Objects.requireNonNull(cbrCase, "cbrCase required");
    if (!(score >= -1.0 && score <= 1.0))
        throw new IllegalArgumentException("score must be in [-1,1], got: " + score);
}
```

The inverted range check `!(score >= -1.0 && score <= 1.0)` naturally rejects NaN (IEEE 754: all NaN comparisons return false) and Infinity without separate checks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -DfailIfNoTests=false`
Expected: ALL PASS (including existing CbrCaseTest tests).

- [ ] **Step 5: Commit**

```
fix(#79): ScoredCbrCase score validation [-1,1] with NaN rejection
```

---

### Task 2: CaseMemoryStore scan SPI

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryCapability.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryScanRequest.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/CaseMemoryStore.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/CaseMemoryStoreSpiTest.java`

**Interfaces:**
- Consumes: `MemoryCapability` enum, `MemoryCapabilityException`, `CaseMemoryStore`, `Memory`
- Produces: `MemoryCapability.SCAN`, `MemoryScanRequest` record, `CaseMemoryStore.scan(MemoryScanRequest)` default method

- [ ] **Step 1: Write the failing tests**

Add to `CaseMemoryStoreSpiTest.java`:

```java
@Test
void scan_default_throws_MemoryCapabilityException() {
    var request = new MemoryScanRequest("tenant-1", null, null, null, 10, null);
    final var ex = assertThrows(MemoryCapabilityException.class,
        () -> sut.scan(request));
    assertEquals(MemoryCapability.SCAN, ex.required());
}
```

Also create a new test class `memory-api/src/test/java/io/casehub/neocortex/memory/MemoryScanRequestTest.java`:

```java
package io.casehub.neocortex.memory;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class MemoryScanRequestTest {

    @Test
    void requiresTenantId() {
        assertThrows(NullPointerException.class,
            () -> new MemoryScanRequest(null, null, null, null, 10, null));
    }

    @Test
    void requiresPositiveLimit() {
        assertThrows(IllegalArgumentException.class,
            () -> new MemoryScanRequest("t1", null, null, null, 0, null));
    }

    @Test
    void rejectsAttributeValueWithoutKey() {
        assertThrows(IllegalArgumentException.class,
            () -> new MemoryScanRequest("t1", null, null, "val", 10, null));
    }

    @Test
    void rejectsAttributeKeyWithoutValue() {
        assertThrows(IllegalArgumentException.class,
            () -> new MemoryScanRequest("t1", null, "key", null, 10, null));
    }

    @Test
    void acceptsNoFilter() {
        var r = new MemoryScanRequest("t1", null, null, null, 10, null);
        assertEquals("t1", r.tenantId());
        assertNull(r.attributeKey());
    }

    @Test
    void acceptsKeyValuePair() {
        var r = new MemoryScanRequest("t1", null, "cbr.caseType", "aml", 10, null);
        assertEquals("cbr.caseType", r.attributeKey());
        assertEquals("aml", r.attributeValue());
    }

    @Test
    void acceptsDomainFilter() {
        var r = new MemoryScanRequest("t1", "cbr", null, null, 10, null);
        assertEquals("cbr", r.domain());
    }

    @Test
    void acceptsCursor() {
        var r = new MemoryScanRequest("t1", null, null, null, 10, "mem-abc");
        assertEquals("mem-abc", r.afterMemoryId());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="CaseMemoryStoreSpiTest#scan_default_throws_MemoryCapabilityException,MemoryScanRequestTest" -DfailIfNoTests=false`
Expected: FAIL — classes do not exist yet.

- [ ] **Step 3: Implement the SPI additions**

Add `SCAN` to `MemoryCapability.java` — add after the erasure section:

```java
// Admin / scan tier
SCAN,            // paginated attribute-filtered enumeration
```

Create `MemoryScanRequest.java`:

```java
package io.casehub.neocortex.memory;

import java.util.Objects;

public record MemoryScanRequest(
    String tenantId,
    String domain,
    String attributeKey,
    String attributeValue,
    int limit,
    String afterMemoryId
) {
    public MemoryScanRequest {
        Objects.requireNonNull(tenantId, "tenantId required");
        if (limit < 1)
            throw new IllegalArgumentException("limit must be >= 1, got: " + limit);
        if (attributeValue != null && attributeKey == null)
            throw new IllegalArgumentException("attributeValue requires attributeKey");
        if (attributeKey != null && attributeValue == null)
            throw new IllegalArgumentException("attributeKey requires attributeValue for filtered scan");
    }
}
```

Add default `scan()` to `CaseMemoryStore.java` — after `requireCapability()`:

```java
default List<Memory> scan(MemoryScanRequest request) {
    throw new MemoryCapabilityException(MemoryCapability.SCAN, getClass());
}
```

Add the `MemoryScanRequest` import to `CaseMemoryStore.java`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -DfailIfNoTests=false`
Expected: ALL PASS.

- [ ] **Step 5: Verify full build still passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS — default method means no compilation breakage in any module.

- [ ] **Step 6: Commit**

```
feat(#74): CaseMemoryStore scan SPI — MemoryCapability.SCAN, MemoryScanRequest, default scan()
```

---

### Task 3: JpaMemoryStore scan implementation

**Files:**
- Modify: `memory-jpa/src/main/java/io/casehub/neocortex/memory/jpa/JpaMemoryStore.java`
- Modify: `memory-jpa/src/test/java/io/casehub/neocortex/memory/jpa/JpaMemoryStoreTest.java`

**Interfaces:**
- Consumes: `MemoryScanRequest`, `MemoryCapability.SCAN`, `Memory`, `MemoryPermissions`
- Produces: `JpaMemoryStore.scan(MemoryScanRequest)` — native SQL with conditional `::jsonb->>` and `memory_id >` clauses

- [ ] **Step 1: Write the failing tests**

Add to `JpaMemoryStoreTest.java`. The tests store entries via the existing `store()` method, then scan. Check that the test class already has store/inject infrastructure — it uses `@QuarkusTest` with PostgreSQL DevServices.

```java
@Test
void scan_returnsEntriesMatchingAttribute() {
    // Store two CBR entries and one non-CBR entry
    store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-1", "problem 1",
        Map.of("cbr.caseType", "aml", "solution", "sol1")));
    store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-2", "problem 2",
        Map.of("cbr.caseType", "aml", "solution", "sol2")));
    store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-3", "problem 3",
        Map.of("other", "value")));

    var request = new MemoryScanRequest(TENANT, null, "cbr.caseType", "aml", 100, null);
    var results = store.scan(request);

    assertThat(results).hasSize(2);
    assertThat(results).allSatisfy(m ->
        assertThat(m.attributes()).containsEntry("cbr.caseType", "aml"));
}

@Test
void scan_respectsLimit() {
    for (int i = 0; i < 5; i++) {
        store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-" + i, "p" + i,
            Map.of("cbr.caseType", "aml")));
    }
    var request = new MemoryScanRequest(TENANT, null, "cbr.caseType", "aml", 2, null);
    var results = store.scan(request);
    assertThat(results).hasSize(2);
}

@Test
void scan_paginatesWithCursor() {
    for (int i = 0; i < 5; i++) {
        store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-" + i, "p" + i,
            Map.of("cbr.caseType", "aml")));
    }
    // First page
    var page1 = store.scan(new MemoryScanRequest(TENANT, null, "cbr.caseType", "aml", 3, null));
    assertThat(page1).hasSize(3);

    // Second page using cursor from last element
    String cursor = page1.getLast().memoryId();
    var page2 = store.scan(new MemoryScanRequest(TENANT, null, "cbr.caseType", "aml", 3, cursor));
    assertThat(page2).hasSize(2);

    // No overlap
    var page1Ids = page1.stream().map(Memory::memoryId).toList();
    var page2Ids = page2.stream().map(Memory::memoryId).toList();
    assertThat(page1Ids).doesNotContainAnyElementsOf(page2Ids);
}

@Test
void scan_filtersByTenant() {
    store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-1", "p1",
        Map.of("cbr.caseType", "aml")));
    store.store(new MemoryInput("e1", DOMAIN, "other-tenant", "case-2", "p2",
        Map.of("cbr.caseType", "aml")));

    var results = store.scan(new MemoryScanRequest(TENANT, null, "cbr.caseType", "aml", 100, null));
    assertThat(results).hasSize(1);
}

@Test
void scan_filtersByDomain() {
    store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-1", "p1",
        Map.of("cbr.caseType", "aml")));
    store.store(new MemoryInput("e1", new MemoryDomain("other"), TENANT, "case-2", "p2",
        Map.of("cbr.caseType", "aml")));

    var results = store.scan(new MemoryScanRequest(TENANT, DOMAIN.name(), "cbr.caseType", "aml", 100, null));
    assertThat(results).hasSize(1);
}

@Test
void scan_withoutAttributeFilter_returnsAllForTenant() {
    store.store(new MemoryInput("e1", DOMAIN, TENANT, "case-1", "p1", Map.of("a", "1")));
    store.store(new MemoryInput("e2", DOMAIN, TENANT, "case-2", "p2", Map.of("b", "2")));
    store.store(new MemoryInput("e1", DOMAIN, "other", "case-3", "p3", Map.of("c", "3")));

    var results = store.scan(new MemoryScanRequest(TENANT, null, null, null, 100, null));
    assertThat(results).hasSize(2);
}

@Test
void scan_declaresScanCapability() {
    assertThat(store.capabilities()).contains(MemoryCapability.SCAN);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-jpa -Dtest="JpaMemoryStoreTest#scan*" -DfailIfNoTests=false`
Expected: FAIL — `scan()` not overridden, throws `MemoryCapabilityException`.

- [ ] **Step 3: Implement JpaMemoryStore.scan()**

Add to `JpaMemoryStore.java`:

1. Add `MemoryCapability.SCAN` to the `capabilities()` set.

2. Add the `scan()` method:

```java
@Timed(value = "casehub.memory.jpa", histogram = true, extraTags = {"operation", "scan"})
@Override
@Transactional(TxType.REQUIRED)
public List<Memory> scan(MemoryScanRequest request) {
    MemoryPermissions.assertTenant(request.tenantId(), principal, requestContextActive());

    var sql = new StringBuilder("SELECT * FROM memory_entry WHERE tenant_id = :tenantId");
    if (request.domain() != null) sql.append(" AND domain = :domain");
    if (request.attributeKey() != null)
        sql.append(" AND attributes::jsonb->>:attrKey = :attrValue");
    if (request.afterMemoryId() != null) sql.append(" AND memory_id > :cursor");
    sql.append(" ORDER BY memory_id ASC");

    @SuppressWarnings("unchecked")
    var nq = em.createNativeQuery(sql.toString(), MemoryEntry.class)
        .setParameter("tenantId", request.tenantId())
        .setMaxResults(request.limit());

    if (request.domain() != null) nq.setParameter("domain", request.domain());
    if (request.attributeKey() != null) {
        nq.setParameter("attrKey", request.attributeKey());
        nq.setParameter("attrValue", request.attributeValue());
    }
    if (request.afterMemoryId() != null) nq.setParameter("cursor", request.afterMemoryId());

    return ((List<MemoryEntry>) nq.getResultList()).stream().map(this::toMemory).toList();
}
```

Add import for `MemoryScanRequest`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-jpa -DfailIfNoTests=false`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```
feat(#74): JpaMemoryStore scan implementation — jsonb attribute filter with cursor pagination
```

---

### Task 4: SqliteMemoryStore scan implementation

**Files:**
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java`
- Modify: `memory-sqlite/src/test/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStoreTest.java`

**Interfaces:**
- Consumes: `MemoryScanRequest`, `MemoryCapability.SCAN`, `Memory`, `MemoryPermissions`
- Produces: `SqliteMemoryStore.scan(MemoryScanRequest)` — JDBC with `json_extract` and quoted key syntax

- [ ] **Step 1: Write the failing tests**

Add the same seven test methods as Task 3 to `SqliteMemoryStoreTest.java`, adapted for SQLite test infrastructure (the test class uses `@QuarkusTest` with SQLite file). Use the same test names: `scan_returnsEntriesMatchingAttribute`, `scan_respectsLimit`, `scan_paginatesWithCursor`, `scan_filtersByTenant`, `scan_filtersByDomain`, `scan_withoutAttributeFilter_returnsAllForTenant`, `scan_declaresScanCapability`.

The test data setup and assertions are identical to Task 3 — the SPI contract is the same.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-sqlite -Dtest="SqliteMemoryStoreTest#scan*" -DfailIfNoTests=false`
Expected: FAIL — `scan()` not overridden.

- [ ] **Step 3: Implement SqliteMemoryStore.scan()**

1. Add `MemoryCapability.SCAN` to the `capabilities()` set.

2. Add the `scan()` method. Follow the existing JDBC pattern used by `erase()`, `eraseById()`, etc.:

```java
@Timed(value = "casehub.memory.sqlite", histogram = true, extraTags = {"operation", "scan"})
@Override
public List<Memory> scan(MemoryScanRequest request) {
    MemoryPermissions.assertTenant(request.tenantId(), principal, requestContextActive());

    var sql = new StringBuilder("SELECT * FROM memory_entry WHERE tenant_id = ?");
    if (request.domain() != null) sql.append(" AND domain = ?");
    if (request.attributeKey() != null)
        sql.append(" AND json_extract(attributes, '$.\"' || ? || '\"') = ?");
    if (request.afterMemoryId() != null) sql.append(" AND memory_id > ?");
    sql.append(" ORDER BY memory_id ASC LIMIT ?");

    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement(sql.toString())) {
        int idx = 1;
        ps.setString(idx++, request.tenantId());
        if (request.domain() != null) ps.setString(idx++, request.domain());
        if (request.attributeKey() != null) {
            ps.setString(idx++, request.attributeKey());
            ps.setString(idx++, request.attributeValue());
        }
        if (request.afterMemoryId() != null) ps.setString(idx++, request.afterMemoryId());
        ps.setInt(idx, request.limit());

        var results = new ArrayList<Memory>();
        try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) results.add(toMemory(rs));
        }
        return List.copyOf(results);
    } catch (SQLException e) {
        throw new IllegalStateException("scan() failed", e);
    }
}
```

Note: SQLite's `json_extract` with quoted key `'$."cbr.caseType"'` uses string concatenation in the SQL. The `?` placeholder provides the key name; the quoting is in the SQL template itself. This prevents `.` in key names from being interpreted as JSON path separators.

Add import for `MemoryScanRequest`, `ArrayList`, `Memory`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-sqlite -DfailIfNoTests=false`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```
feat(#74): SqliteMemoryStore scan implementation — json_extract with quoted key pagination
```

---

### Task 5: Dimension migration config gate + effectiveDim fix + INFO log test (#78, #79)

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrConfig.java`
- Create: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrDimensionMismatchException.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `QdrantCbrConfig`, `CbrCollectionManager`, `QdrantClient`
- Produces: `QdrantCbrConfig.allowDimensionMigration()`, `CbrDimensionMismatchException`, gated `ensureCollection()`, hoisted `effectiveDim`

- [ ] **Step 1: Write the failing tests**

Add to `QdrantCbrCaseMemoryStoreTest.java`. These test the dimension gate and the INFO log path. The test creates stores with different configurations.

```java
@Test
void ensureCollection_throwsOnDimensionMismatch_whenMigrationDisabled() {
    // Create store with dim=1 (no embedding model), store a case to create collection
    var store1 = createStore(null, false);
    store1.registerSchema(CbrFeatureSchema.of("dim-test",
        FeatureField.categorical("cat")));
    store1.store(new TextualCbrCase("p", "s", null, null),
        "dim-test", ENTITY, CBR, TENANT, "case-1");

    // Create a second store with a mock embedding model that reports dim=4
    // This triggers dimension mismatch on next ensureCollection() call
    var store2 = createStore(new StubEmbeddingModel(4), false);
    assertThatThrownBy(() ->
        store2.store(new TextualCbrCase("p2", "s2", null, null),
            "dim-test", ENTITY, CBR, TENANT, "case-2"))
        .isInstanceOf(CbrDimensionMismatchException.class);
}

@Test
void ensureCollection_recreatesCollection_whenMigrationEnabled() {
    var store1 = createStore(null, false);
    store1.registerSchema(CbrFeatureSchema.of("dim-migrate",
        FeatureField.categorical("cat")));
    store1.store(new TextualCbrCase("p", "s", null, null),
        "dim-migrate", ENTITY, CBR, TENANT, "case-1");

    // Enabling migration allows recreation
    var store2 = createStore(new StubEmbeddingModel(4), true);
    store2.registerSchema(CbrFeatureSchema.of("dim-migrate",
        FeatureField.categorical("cat")));
    assertThatCode(() ->
        store2.store(new TextualCbrCase("p2", "s2", null, null),
            "dim-migrate", ENTITY, CBR, TENANT, "case-2"))
        .doesNotThrowAnyException();
}

@Test
void retrieveSimilar_withProblem_noEmbeddingModel_logsInfo() {
    var handler = new java.util.logging.Handler() {
        final java.util.List<java.util.logging.LogRecord> records =
            java.util.Collections.synchronizedList(new java.util.ArrayList<>());
        @Override public void publish(java.util.logging.LogRecord r) { records.add(r); }
        @Override public void flush() {}
        @Override public void close() {}
    };
    var logger = java.util.logging.Logger.getLogger(
        "io.casehub.neocortex.memory.cbr.qdrant.QdrantCbrCaseMemoryStore");
    logger.addHandler(handler);
    try {
        var s = store(); // uses null embeddingModel
        s.registerSchema(CbrFeatureSchema.of("log-test",
            FeatureField.categorical("cat")));
        s.store(new FeatureVectorCbrCase("problem", "solution", null, null,
            Map.of("cat", "A")), "log-test", ENTITY, CBR, TENANT, "case-log");

        s.retrieveSimilar(CbrQuery.of(TENANT, CBR, "log-test",
            Map.of("cat", "A"), 5).withProblem("query text"), FeatureVectorCbrCase.class);

        assertThat(handler.records).anyMatch(r ->
            r.getLevel() == java.util.logging.Level.INFO
            && r.getMessage().contains("Dense search unavailable"));
    } finally {
        logger.removeHandler(handler);
    }
}
```

The test requires helper methods. Add to the test class:

```java
private QdrantCbrCaseMemoryStore createStore(EmbeddingModel embeddingModel, boolean allowMigration) {
    int testId = TEST_COUNTER.incrementAndGet();
    QdrantCbrConfig config = testConfig(testId, allowMigration);
    QdrantClient client = new QdrantClient(
        QdrantGrpcClient.newBuilder(qdrant.getHost(), qdrant.getMappedPort(6334), false).build());
    var collectionManager = new CbrCollectionManager(client, config);
    return new QdrantCbrCaseMemoryStore(collectionManager, embeddingModel, config, null);
}

private QdrantCbrConfig testConfig(int testId, boolean allowMigration) {
    return new QdrantCbrConfig() {
        @Override public String host() { return qdrant.getHost(); }
        @Override public int port() { return qdrant.getMappedPort(6334); }
        @Override public Optional<String> apiKey() { return Optional.empty(); }
        @Override public boolean useTls() { return false; }
        @Override public String collectionPrefix() { return "cbr_test_" + testId; }
        @Override public String denseVectorName() { return "dense"; }
        @Override public int maxRetries() { return 3; }
        @Override public boolean allowDimensionMigration() { return allowMigration; }
    };
}
```

Also add a minimal `StubEmbeddingModel` inner class (or import from LangChain4j test fixtures):

```java
private record StubEmbeddingModel(int dim) implements EmbeddingModel {
    @Override public dev.langchain4j.model.output.Response<Embedding> embed(String text) {
        float[] vec = new float[dim];
        return new dev.langchain4j.model.output.Response<>(new Embedding(vec));
    }
    @Override public dev.langchain4j.model.output.Response<Embedding> embed(TextSegment segment) {
        return embed(segment.text());
    }
    @Override public int dimension() { return dim; }
}
```

Update the existing `store()` factory method to use `testConfig`:
```java
@Override
protected CbrCaseMemoryStore store() {
    if (qdrantStore == null) {
        qdrantStore = createStore(null, false);
    }
    return qdrantStore;
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest="QdrantCbrCaseMemoryStoreTest#ensureCollection*,QdrantCbrCaseMemoryStoreTest#retrieveSimilar_withProblem_noEmbeddingModel_logsInfo" -DfailIfNoTests=false`
Expected: FAIL — `allowDimensionMigration()` does not exist, `CbrDimensionMismatchException` does not exist.

- [ ] **Step 3: Implement the config and exception**

Add to `QdrantCbrConfig.java`:
```java
@WithDefault("false")
boolean allowDimensionMigration();
```

Create `CbrDimensionMismatchException.java`:
```java
package io.casehub.neocortex.memory.cbr.qdrant;

public class CbrDimensionMismatchException extends RuntimeException {
    private final String collection;
    private final int existingDimension;
    private final int requestedDimension;

    public CbrDimensionMismatchException(String collection, int existingDimension, int requestedDimension) {
        super("Dimension mismatch in collection " + collection + ": existing=" + existingDimension
            + ", requested=" + requestedDimension
            + ". Set casehub.memory.cbr.qdrant.allow-dimension-migration=true to allow destructive recreation.");
        this.collection = collection;
        this.existingDimension = existingDimension;
        this.requestedDimension = requestedDimension;
    }

    public String collection() { return collection; }
    public int existingDimension() { return existingDimension; }
    public int requestedDimension() { return requestedDimension; }
}
```

- [ ] **Step 4: Modify CbrCollectionManager.ensureCollection()**

Replace the `ensureCollection` method. Key changes:
1. Hoist `effectiveDim` to method top (fixes #79 duplication)
2. Gate dimension mismatch on `config.allowDimensionMigration()`
3. Improve LOG.warning message to mention all tenants affected

```java
void ensureCollection(String caseType, int vectorDimension) {
    String collection = collectionName(caseType);
    if (knownCollections.contains(collection)) {
        return;
    }

    int effectiveDim = vectorDimension > 0 ? vectorDimension : 1;

    try {
        if (client.collectionExistsAsync(collection).get()) {
            var info = client.getCollectionInfoAsync(collection).get();
            var vectorsConfig = info.getConfig().getParams().getVectorsConfig();
            if (vectorsConfig.hasParamsMap()) {
                var params = vectorsConfig.getParamsMap().getMapMap().get(config.denseVectorName());
                if (params != null && params.getSize() != effectiveDim) {
                    if (!config.allowDimensionMigration()) {
                        throw new CbrDimensionMismatchException(collection, (int) params.getSize(), effectiveDim);
                    }
                    LOG.warning("Collection " + collection + " dimension mismatch ("
                        + params.getSize() + " → " + effectiveDim
                        + ") — recreating. ALL tenants sharing caseType=" + caseType
                        + " are affected. Run reconciliation per tenant to recover data.");
                    client.deleteCollectionAsync(collection).get();
                } else {
                    knownCollections.add(collection);
                    return;
                }
            } else {
                knownCollections.add(collection);
                return;
            }
        }

        VectorParams denseParams = VectorParams.newBuilder()
            .setSize(effectiveDim)
            .setDistance(Distance.Cosine)
            .build();

        CreateCollection.Builder createBuilder = CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(VectorsConfig.newBuilder()
                .setParamsMap(VectorParamsMap.newBuilder()
                    .putMap(config.denseVectorName(), denseParams)
                    .build())
                .build());

        client.createCollectionAsync(createBuilder.build()).get();
        createBasePayloadIndexes(collection);
        knownCollections.add(collection);

    } catch (CbrDimensionMismatchException e) {
        throw e;
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new RuntimeException("Interrupted during ensureCollection", e);
    } catch (ExecutionException e) {
        throw new RuntimeException("ensureCollection failed for " + collection, e.getCause());
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -DfailIfNoTests=false`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```
fix(#78): gate dimension-mismatch recovery behind config flag + fix(#79): hoist effectiveDim, INFO log test
```

---

### Task 6: CbrAttributeKeys + CbrMemoryDeserializer + round-trip test

**Files:**
- Create: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrAttributeKeys.java`
- Create: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrMemoryDeserializer.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` (refactor string literals to use CbrAttributeKeys)
- Create: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrMemoryDeserializerTest.java`

**Interfaces:**
- Consumes: `CbrCase`, `FeatureVectorCbrCase`, `PlanCbrCase`, `TextualCbrCase`, `PlanTrace`, `MemoryAttributeKeys`, `Memory`, `MemoryInput`, `MemoryDomain`
- Produces: `CbrAttributeKeys` (string constants), `CbrMemoryDeserializer.deserialize(Memory) → Optional<CbrCase>`

- [ ] **Step 1: Write the failing round-trip tests**

Create `CbrMemoryDeserializerTest.java`:

```java
package io.casehub.neocortex.memory.cbr.qdrant;

import io.casehub.neocortex.memory.*;
import io.casehub.neocortex.memory.cbr.*;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class CbrMemoryDeserializerTest {

    private static final MemoryDomain CBR = new MemoryDomain("cbr");
    private static final String TENANT = "test-tenant";
    private static final String ENTITY = "test-entity";

    @Test
    void roundTrip_featureVectorCbrCase() {
        var original = new FeatureVectorCbrCase("Zerg rush detected", "wall-off and expand",
            "WIN", 0.85, Map.of("opponent_race", "Zerg", "army_size_ratio", 0.7));

        var deserialized = roundTrip(original, "starcraft-game");

        assertThat(deserialized).isPresent();
        assertThat(deserialized.get()).isInstanceOf(FeatureVectorCbrCase.class);
        var fv = (FeatureVectorCbrCase) deserialized.get();
        assertThat(fv.problem()).isEqualTo("Zerg rush detected");
        assertThat(fv.solution()).isEqualTo("wall-off and expand");
        assertThat(fv.outcome()).isEqualTo("WIN");
        assertThat(fv.confidence()).isEqualTo(0.85);
        assertThat(fv.features()).containsEntry("opponent_race", "Zerg");
    }

    @Test
    void roundTrip_planCbrCase() {
        var trace = new PlanTrace("scout", "reconnaissance", "drone-scout", "SUCCESS", 1,
            Map.of("duration", 30));
        var original = new PlanCbrCase("Zerg rush", "early pressure", "WIN", 0.9,
            Map.of("opponent_race", "Zerg"), List.of(trace));

        var deserialized = roundTrip(original, "starcraft-game");

        assertThat(deserialized).isPresent();
        assertThat(deserialized.get()).isInstanceOf(PlanCbrCase.class);
        var plan = (PlanCbrCase) deserialized.get();
        assertThat(plan.problem()).isEqualTo("Zerg rush");
        assertThat(plan.planTrace()).hasSize(1);
        assertThat(plan.planTrace().get(0).bindingName()).isEqualTo("scout");
    }

    @Test
    void roundTrip_textualCbrCase() {
        var original = new TextualCbrCase("simple problem", "simple solution", "OK", 0.5);

        var deserialized = roundTrip(original, "simple-type");

        assertThat(deserialized).isPresent();
        assertThat(deserialized.get()).isInstanceOf(TextualCbrCase.class);
        var t = (TextualCbrCase) deserialized.get();
        assertThat(t.problem()).isEqualTo("simple problem");
        assertThat(t.solution()).isEqualTo("simple solution");
        assertThat(t.outcome()).isEqualTo("OK");
        assertThat(t.confidence()).isEqualTo(0.5);
    }

    @Test
    void roundTrip_nullOptionalFields() {
        var original = new TextualCbrCase("p", "s", null, null);

        var deserialized = roundTrip(original, "minimal");

        assertThat(deserialized).isPresent();
        assertThat(deserialized.get().outcome()).isNull();
        assertThat(deserialized.get().confidence()).isNull();
    }

    @Test
    void deserialize_unknownCbrType_returnsEmpty() {
        var memory = new Memory("mem-1", ENTITY, CBR, TENANT, "case-1",
            "problem", Map.of(CbrAttributeKeys.CBR_TYPE, "unknown",
                              "solution", "sol"), Instant.now());
        assertThat(CbrMemoryDeserializer.deserialize(memory)).isEmpty();
    }

    @Test
    void deserialize_missingCbrType_returnsEmpty() {
        var memory = new Memory("mem-1", ENTITY, CBR, TENANT, "case-1",
            "problem", Map.of("solution", "sol"), Instant.now());
        assertThat(CbrMemoryDeserializer.deserialize(memory)).isEmpty();
    }

    @Test
    void deserialize_missingSolution_returnsEmpty() {
        var memory = new Memory("mem-1", ENTITY, CBR, TENANT, "case-1",
            "problem", Map.of(CbrAttributeKeys.CBR_TYPE, "textual"), Instant.now());
        assertThat(CbrMemoryDeserializer.deserialize(memory)).isEmpty();
    }

    @Test
    void deserialize_malformedFeaturesJson_returnsEmpty() {
        var memory = new Memory("mem-1", ENTITY, CBR, TENANT, "case-1",
            "problem", Map.of(CbrAttributeKeys.CBR_TYPE, FeatureVectorCbrCase.CBR_TYPE,
                              "solution", "sol",
                              CbrAttributeKeys.CBR_FEATURES, "not valid json"),
            Instant.now());
        assertThat(CbrMemoryDeserializer.deserialize(memory)).isEmpty();
    }

    private java.util.Optional<CbrCase> roundTrip(CbrCase original, String caseType) {
        // Serialize using the same code path as QdrantCbrCaseMemoryStore
        MemoryInput input = serializeToMemoryInput(original, ENTITY, CBR, TENANT, "case-1", caseType);
        // Convert to Memory (simulating what CaseMemoryStore.store() → query() returns)
        Memory memory = new Memory("mem-1", input.entityId(), input.domain(), input.tenantId(),
            input.caseId(), input.text(), input.attributes(), Instant.now());
        return CbrMemoryDeserializer.deserialize(memory);
    }

    /**
     * Package-private access to serialization — calls the same static method
     * that QdrantCbrCaseMemoryStore uses internally.
     */
    private static MemoryInput serializeToMemoryInput(CbrCase cbrCase, String entityId,
                                                       MemoryDomain domain, String tenantId,
                                                       String caseId, String caseType) {
        // Replicates QdrantCbrCaseMemoryStore.serializeToMemoryInput() logic
        // After refactoring to CbrAttributeKeys, both paths use the same constants
        return CbrMemorySerializer.serialize(cbrCase, entityId, domain, tenantId, caseId, caseType);
    }
}
```

Note: The round-trip test requires extracting serialization into a `CbrMemorySerializer` static utility (the inverse of `CbrMemoryDeserializer`). This is a refactoring of the existing `serializeToMemoryInput()` private method in `QdrantCbrCaseMemoryStore`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest="CbrMemoryDeserializerTest" -DfailIfNoTests=false`
Expected: FAIL — classes do not exist.

- [ ] **Step 3: Create CbrAttributeKeys**

```java
package io.casehub.neocortex.memory.cbr.qdrant;

public final class CbrAttributeKeys {
    public static final String CBR_TYPE = "cbr.type";
    public static final String CBR_FEATURES = "cbr.features";
    public static final String CBR_PLAN_TRACE = "cbr.planTrace";
    public static final String CBR_CASE_TYPE = "cbr.caseType";
    private CbrAttributeKeys() {}
}
```

- [ ] **Step 4: Create CbrMemorySerializer (extract from QdrantCbrCaseMemoryStore)**

Extract the `serializeToMemoryInput()` method from `QdrantCbrCaseMemoryStore` into a static utility class:

```java
package io.casehub.neocortex.memory.cbr.qdrant;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.neocortex.memory.MemoryAttributeKeys;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryInput;
import io.casehub.neocortex.memory.cbr.CbrCase;
import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import java.util.HashMap;
import java.util.Map;

final class CbrMemorySerializer {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private CbrMemorySerializer() {}

    static MemoryInput serialize(CbrCase cbrCase, String entityId,
                                  MemoryDomain domain, String tenantId,
                                  String caseId, String caseType) {
        Map<String, String> attributes = new HashMap<>();
        attributes.put(MemoryAttributeKeys.SOLUTION, cbrCase.solution());
        if (cbrCase.outcome() != null)
            attributes.put(MemoryAttributeKeys.OUTCOME, cbrCase.outcome());
        if (cbrCase.confidence() != null)
            attributes.put(MemoryAttributeKeys.CONFIDENCE,
                MemoryAttributeKeys.formatConfidence(cbrCase.confidence()));

        attributes.put(CbrAttributeKeys.CBR_TYPE, cbrCase.cbrType());
        Map<String, Object> features = cbrCase.features();
        if (!features.isEmpty()) {
            try {
                attributes.put(CbrAttributeKeys.CBR_FEATURES, MAPPER.writeValueAsString(features));
            } catch (JsonProcessingException e) {
                throw new RuntimeException("Failed to serialize features to JSON", e);
            }
        }
        if (cbrCase instanceof PlanCbrCase plan) {
            try {
                attributes.put(CbrAttributeKeys.CBR_PLAN_TRACE, MAPPER.writeValueAsString(plan.planTrace()));
            } catch (JsonProcessingException e) {
                throw new RuntimeException("Failed to serialize plan trace to JSON", e);
            }
        }
        attributes.put(CbrAttributeKeys.CBR_CASE_TYPE, caseType);

        return new MemoryInput(entityId, domain, tenantId, caseId, cbrCase.problem(), attributes);
    }
}
```

Then refactor `QdrantCbrCaseMemoryStore.serializeToMemoryInput()` to delegate:

```java
private MemoryInput serializeToMemoryInput(CbrCase cbrCase, String entityId,
                                            MemoryDomain domain, String tenantId,
                                            String caseId, String caseType) {
    return CbrMemorySerializer.serialize(cbrCase, entityId, domain, tenantId, caseId, caseType);
}
```

- [ ] **Step 5: Create CbrMemoryDeserializer**

```java
package io.casehub.neocortex.memory.cbr.qdrant;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryAttributeKeys;
import io.casehub.neocortex.memory.cbr.*;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.logging.Level;
import java.util.logging.Logger;

final class CbrMemoryDeserializer {
    private static final Logger LOG = Logger.getLogger(CbrMemoryDeserializer.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};
    private static final TypeReference<List<PlanTrace>> PLAN_TRACE_TYPE = new TypeReference<>() {};

    private CbrMemoryDeserializer() {}

    static Optional<CbrCase> deserialize(Memory memory) {
        try {
            String problem = memory.text();
            Map<String, String> attrs = memory.attributes();

            String solution = attrs.get(MemoryAttributeKeys.SOLUTION);
            if (solution == null) {
                LOG.warning("Missing solution attribute in memory " + memory.memoryId());
                return Optional.empty();
            }

            String outcome = attrs.get(MemoryAttributeKeys.OUTCOME);
            Double confidence = attrs.containsKey(MemoryAttributeKeys.CONFIDENCE)
                ? MemoryAttributeKeys.parseConfidence(attrs.get(MemoryAttributeKeys.CONFIDENCE))
                : null;

            String cbrType = attrs.get(CbrAttributeKeys.CBR_TYPE);
            if (cbrType == null) {
                LOG.warning("Missing cbr.type attribute in memory " + memory.memoryId());
                return Optional.empty();
            }

            return Optional.of(switch (cbrType) {
                case FeatureVectorCbrCase.CBR_TYPE -> {
                    Map<String, Object> features = parseFeatures(attrs);
                    yield new FeatureVectorCbrCase(problem, solution, outcome, confidence, features);
                }
                case PlanCbrCase.CBR_TYPE -> {
                    Map<String, Object> features = parseFeatures(attrs);
                    List<PlanTrace> planTrace = parsePlanTrace(attrs);
                    yield new PlanCbrCase(problem, solution, outcome, confidence, features, planTrace);
                }
                case TextualCbrCase.CBR_TYPE ->
                    new TextualCbrCase(problem, solution, outcome, confidence);
                default -> {
                    LOG.warning("Unknown cbr.type '" + cbrType + "' in memory " + memory.memoryId());
                    yield null;
                }
            });
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to deserialize memory " + memory.memoryId(), e);
            return Optional.empty();
        }
    }

    private static Map<String, Object> parseFeatures(Map<String, String> attrs) {
        String json = attrs.get(CbrAttributeKeys.CBR_FEATURES);
        if (json == null) return Map.of();
        try {
            return MAPPER.readValue(json, MAP_TYPE);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Malformed cbr.features JSON", e);
        }
    }

    private static List<PlanTrace> parsePlanTrace(Map<String, String> attrs) {
        String json = attrs.get(CbrAttributeKeys.CBR_PLAN_TRACE);
        if (json == null) return List.of();
        try {
            return MAPPER.readValue(json, PLAN_TRACE_TYPE);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Malformed cbr.planTrace JSON", e);
        }
    }
}
```

Note: the `default -> yield null;` in the switch makes the wrapping `Optional.of()` produce `Optional.empty()` indirectly — actually `Optional.of(null)` throws NPE. Fix: use `Optional.ofNullable()` for the switch result. Or restructure:

```java
CbrCase result = switch (cbrType) { ... default -> null; };
if (result == null) return Optional.empty();
return Optional.of(result);
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -DfailIfNoTests=false`
Expected: ALL PASS (including existing tests — refactoring must not break them).

- [ ] **Step 7: Commit**

```
feat(#74): CbrAttributeKeys, CbrMemorySerializer, CbrMemoryDeserializer with round-trip tests
```

---

### Task 7: CbrReconciliationService + CDI wiring + integration test

**Files:**
- Create: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/ReconciliationResult.java`
- Create: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationService.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrBeanProducer.java`
- Create: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationServiceTest.java`

**Interfaces:**
- Consumes: `CbrCollectionManager`, `CbrPointBuilder`, `CbrMemoryDeserializer`, `CbrMemorySerializer`, `CaseMemoryStore`, `MemoryScanRequest`, `MemoryCapability.SCAN`, `EmbeddingModel`, `QdrantCbrConfig`
- Produces: `CbrReconciliationService.reconcile(String caseType, String tenantId) → ReconciliationResult`

- [ ] **Step 1: Write the failing tests**

Create `CbrReconciliationServiceTest.java`:

```java
package io.casehub.neocortex.memory.cbr.qdrant;

import io.casehub.neocortex.memory.*;
import io.casehub.neocortex.memory.cbr.*;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.*;

@Testcontainers
class CbrReconciliationServiceTest {

    @SuppressWarnings("resource")
    @Container
    static final GenericContainer<?> qdrant = new GenericContainer<>("qdrant/qdrant:v1.18.0")
        .withExposedPorts(6334);

    private static final AtomicInteger TEST_COUNTER = new AtomicInteger();
    private static final MemoryDomain CBR = new MemoryDomain("cbr");
    private static final String TENANT = "test-tenant";
    private static final String ENTITY = "test-entity";

    private QdrantCbrCaseMemoryStore cbrStore;
    private InMemoryDelegateStore delegate;
    private CbrReconciliationService reconciler;
    private CbrCollectionManager collectionManager;
    private QdrantCbrConfig config;

    @BeforeEach
    void setUp() {
        int testId = TEST_COUNTER.incrementAndGet();
        config = testConfig(testId);
        QdrantClient client = new QdrantClient(
            QdrantGrpcClient.newBuilder(qdrant.getHost(), qdrant.getMappedPort(6334), false).build());
        collectionManager = new CbrCollectionManager(client, config);
        delegate = new InMemoryDelegateStore();
        cbrStore = new QdrantCbrCaseMemoryStore(collectionManager, null, config, delegate);
        reconciler = new CbrReconciliationService(collectionManager, null, config, delegate);
    }

    @Test
    void reconcile_noDelegate_returnsNoOp() {
        var service = new CbrReconciliationService(collectionManager, null, config, null);
        var result = service.reconcile("test-type", TENANT);
        assertThat(result.orphansRemoved()).isZero();
        assertThat(result.entriesReindexed()).isZero();
    }

    @Test
    void reconcile_delegateWithoutScan_returnsNoOp() {
        var noScanDelegate = new NoScanDelegateStore();
        var service = new CbrReconciliationService(collectionManager, null, config, noScanDelegate);
        var result = service.reconcile("test-type", TENANT);
        assertThat(result.orphansRemoved()).isZero();
        assertThat(result.entriesReindexed()).isZero();
    }

    @Test
    void reconcile_consistentState_noChanges() {
        cbrStore.registerSchema(CbrFeatureSchema.of("game",
            FeatureField.categorical("race")));
        cbrStore.store(new FeatureVectorCbrCase("p1", "s1", null, null,
            Map.of("race", "Zerg")), "game", ENTITY, CBR, TENANT, "case-1");
        cbrStore.store(new FeatureVectorCbrCase("p2", "s2", null, null,
            Map.of("race", "Protoss")), "game", ENTITY, CBR, TENANT, "case-2");

        var result = reconciler.reconcile("game", TENANT);
        assertThat(result.orphansRemoved()).isZero();
        assertThat(result.entriesReindexed()).isZero();
        assertThat(result.errors()).isZero();
    }

    @Test
    void reconcile_missingFromQdrant_reindexes() {
        // Store via cbrStore (writes to both delegate and Qdrant)
        cbrStore.registerSchema(CbrFeatureSchema.of("reindex-type",
            FeatureField.categorical("cat")));
        cbrStore.store(new FeatureVectorCbrCase("p1", "s1", null, null,
            Map.of("cat", "A")), "reindex-type", ENTITY, CBR, TENANT, "case-1");

        // Delete the Qdrant collection to simulate data loss
        String collection = collectionManager.collectionName("reindex-type");
        try {
            collectionManager.client().deleteCollectionAsync(collection).get();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        var result = reconciler.reconcile("reindex-type", TENANT);
        assertThat(result.entriesReindexed()).isEqualTo(1);
        assertThat(result.orphansRemoved()).isZero();

        // Verify the point is back in Qdrant
        var retrieved = cbrStore.retrieveSimilar(
            CbrQuery.of(TENANT, CBR, "reindex-type", Map.of("cat", "A"), 5),
            FeatureVectorCbrCase.class);
        assertThat(retrieved).hasSize(1);
    }

    @Test
    void reconcile_orphanInQdrant_removes() {
        cbrStore.registerSchema(CbrFeatureSchema.of("orphan-type",
            FeatureField.categorical("cat")));
        cbrStore.store(new FeatureVectorCbrCase("p1", "s1", null, null,
            Map.of("cat", "A")), "orphan-type", ENTITY, CBR, TENANT, "case-1");

        // Remove from delegate (simulating delegate erasure without Qdrant cleanup)
        delegate.eraseAll();

        var result = reconciler.reconcile("orphan-type", TENANT);
        assertThat(result.orphansRemoved()).isEqualTo(1);
        assertThat(result.entriesReindexed()).isZero();

        // Verify Qdrant is empty
        var retrieved = cbrStore.retrieveSimilar(
            CbrQuery.of(TENANT, CBR, "orphan-type", Map.of("cat", "A"), 5),
            FeatureVectorCbrCase.class);
        assertThat(retrieved).isEmpty();
    }

    @Test
    void reconcile_emptyCollection_reindexesAll() {
        // Store entries only in delegate, not in Qdrant
        delegate.storeDirectly("case-1", ENTITY, CBR, TENANT,
            new FeatureVectorCbrCase("p1", "s1", null, null, Map.of("cat", "A")), "reindex-all");

        var result = reconciler.reconcile("reindex-all", TENANT);
        assertThat(result.entriesReindexed()).isEqualTo(1);
    }

    // --- Test doubles ---

    private QdrantCbrConfig testConfig(int testId) {
        return new QdrantCbrConfig() {
            @Override public String host() { return qdrant.getHost(); }
            @Override public int port() { return qdrant.getMappedPort(6334); }
            @Override public Optional<String> apiKey() { return Optional.empty(); }
            @Override public boolean useTls() { return false; }
            @Override public String collectionPrefix() { return "cbr_recon_" + testId; }
            @Override public String denseVectorName() { return "dense"; }
            @Override public int maxRetries() { return 3; }
            @Override public boolean allowDimensionMigration() { return false; }
        };
    }

    /**
     * In-memory CaseMemoryStore that supports SCAN for testing reconciliation.
     */
    static class InMemoryDelegateStore implements CaseMemoryStore {
        private final List<Memory> entries = new ArrayList<>();

        @Override public String store(MemoryInput input) {
            String id = UUID.randomUUID().toString();
            entries.add(new Memory(id, input.entityId(), input.domain(), input.tenantId(),
                input.caseId(), input.text(), input.attributes(), Instant.now()));
            return id;
        }
        @Override public List<Memory> query(MemoryQuery q) { return List.of(); }
        @Override public int erase(EraseRequest r) { return 0; }

        @Override
        public Set<MemoryCapability> capabilities() {
            return Set.of(MemoryCapability.SCAN);
        }

        @Override
        public List<Memory> scan(MemoryScanRequest request) {
            return entries.stream()
                .filter(m -> m.tenantId().equals(request.tenantId()))
                .filter(m -> request.domain() == null || m.domain().name().equals(request.domain()))
                .filter(m -> request.attributeKey() == null
                    || request.attributeValue().equals(m.attributes().get(request.attributeKey())))
                .filter(m -> request.afterMemoryId() == null
                    || m.memoryId().compareTo(request.afterMemoryId()) > 0)
                .sorted(Comparator.comparing(Memory::memoryId))
                .limit(request.limit())
                .toList();
        }

        void storeDirectly(String caseId, String entityId, MemoryDomain domain,
                           String tenantId, CbrCase cbrCase, String caseType) {
            MemoryInput input = CbrMemorySerializer.serialize(
                cbrCase, entityId, domain, tenantId, caseId, caseType);
            store(input);
        }

        void eraseAll() { entries.clear(); }
    }

    static class NoScanDelegateStore implements CaseMemoryStore {
        @Override public String store(MemoryInput i) { return ""; }
        @Override public List<Memory> query(MemoryQuery q) { return List.of(); }
        @Override public int erase(EraseRequest r) { return 0; }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest="CbrReconciliationServiceTest" -DfailIfNoTests=false`
Expected: FAIL — `CbrReconciliationService` and `ReconciliationResult` do not exist.

- [ ] **Step 3: Create ReconciliationResult**

```java
package io.casehub.neocortex.memory.cbr.qdrant;

public record ReconciliationResult(
    String caseType,
    String tenantId,
    int orphansRemoved,
    int entriesReindexed,
    int errors
) {}
```

- [ ] **Step 4: Create CbrReconciliationService**

```java
package io.casehub.neocortex.memory.cbr.qdrant;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import io.casehub.neocortex.memory.*;
import io.casehub.neocortex.memory.cbr.CbrCase;
import io.qdrant.client.ConditionFactory;
import io.qdrant.client.PointIdFactory;
import io.qdrant.client.WithPayloadSelectorFactory;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.ScrollPoints;

import java.util.*;
import java.util.concurrent.ExecutionException;
import java.util.logging.Level;
import java.util.logging.Logger;

public class CbrReconciliationService {

    private static final Logger LOG = Logger.getLogger(CbrReconciliationService.class.getName());
    private static final int DEFAULT_PAGE_SIZE = 100;

    private final CbrCollectionManager collectionManager;
    private final EmbeddingModel embeddingModel;
    private final QdrantCbrConfig config;
    private final CaseMemoryStore delegate;

    CbrReconciliationService(CbrCollectionManager collectionManager,
                              EmbeddingModel embeddingModel,
                              QdrantCbrConfig config,
                              CaseMemoryStore delegate) {
        this.collectionManager = collectionManager;
        this.embeddingModel = embeddingModel;
        this.config = config;
        this.delegate = delegate;
    }

    public ReconciliationResult reconcile(String caseType, String tenantId) {
        if (delegate == null) {
            return new ReconciliationResult(caseType, tenantId, 0, 0, 0);
        }
        if (!delegate.capabilities().contains(MemoryCapability.SCAN)) {
            LOG.info("Reconciliation skipped — delegate does not support SCAN");
            return new ReconciliationResult(caseType, tenantId, 0, 0, 0);
        }

        // Step 1: Build delegate index
        Map<UUID, Memory> delegateIndex = buildDelegateIndex(caseType, tenantId);

        // Step 2: Qdrant intersection — find orphans and consistent entries
        int orphansRemoved = 0;
        String collection = collectionManager.collectionName(caseType);
        try {
            if (collectionManager.client().collectionExistsAsync(collection).get()) {
                orphansRemoved = intersectWithQdrant(collection, tenantId, delegateIndex);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted during reconciliation", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Reconciliation failed", e.getCause());
        }

        // Step 3: Reindex remaining (missing from Qdrant)
        int reindexed = 0;
        int errors = 0;
        if (!delegateIndex.isEmpty()) {
            int vectorDim = embeddingModel != null ? embeddingModel.dimension() : 0;
            collectionManager.ensureCollection(caseType, vectorDim);

            List<PointStruct> batch = new ArrayList<>();
            for (var entry : delegateIndex.entrySet()) {
                try {
                    Memory memory = entry.getValue();
                    Optional<CbrCase> maybeCbrCase = CbrMemoryDeserializer.deserialize(memory);
                    if (maybeCbrCase.isEmpty()) {
                        LOG.warning("Skipping undeserializable memory " + memory.memoryId());
                        errors++;
                        continue;
                    }
                    CbrCase cbrCase = maybeCbrCase.get();

                    Embedding embedding = null;
                    if (embeddingModel != null) {
                        embedding = embeddingModel.embed(TextSegment.from(cbrCase.problem())).content();
                    }

                    PointStruct point = CbrPointBuilder.buildPoint(
                        cbrCase, caseType, memory.entityId(), memory.domain().name(),
                        memory.tenantId(), memory.caseId(), embedding, config.denseVectorName());
                    batch.add(point);
                    reindexed++;
                } catch (Exception e) {
                    LOG.log(Level.WARNING, "Failed to reindex memory " + entry.getValue().memoryId(), e);
                    errors++;
                }
            }
            if (!batch.isEmpty()) {
                try {
                    collectionManager.client().upsertAsync(collection, batch).get();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException("Interrupted during batch upsert", e);
                } catch (ExecutionException e) {
                    throw new RuntimeException("Batch upsert failed", e.getCause());
                }
            }
        }

        return new ReconciliationResult(caseType, tenantId, orphansRemoved, reindexed, errors);
    }

    private Map<UUID, Memory> buildDelegateIndex(String caseType, String tenantId) {
        Map<UUID, Memory> index = new LinkedHashMap<>();
        String cursor = null;
        while (true) {
            var request = new MemoryScanRequest(tenantId, null,
                CbrAttributeKeys.CBR_CASE_TYPE, caseType, DEFAULT_PAGE_SIZE, cursor);
            List<Memory> page = delegate.scan(request);
            for (Memory m : page) {
                if (m.caseId() != null) {
                    UUID pointId = CbrPointBuilder.pointId(tenantId, caseType, m.caseId());
                    index.put(pointId, m);
                }
            }
            if (page.size() < DEFAULT_PAGE_SIZE) break;
            cursor = page.getLast().memoryId();
        }
        return index;
    }

    private int intersectWithQdrant(String collection, String tenantId,
                                     Map<UUID, Memory> delegateIndex)
            throws InterruptedException, ExecutionException {
        int orphansRemoved = 0;
        var filter = io.qdrant.client.grpc.Common.Filter.newBuilder()
            .addMust(ConditionFactory.matchKeyword("tenantId", tenantId))
            .build();

        io.qdrant.client.grpc.Points.PointId nextPageOffset = null;
        boolean hasMore = true;

        while (hasMore) {
            var scrollBuilder = ScrollPoints.newBuilder()
                .setCollectionName(collection)
                .setFilter(filter)
                .setLimit(DEFAULT_PAGE_SIZE)
                .setWithPayload(WithPayloadSelectorFactory.enable(false));

            if (nextPageOffset != null) {
                scrollBuilder.setOffset(nextPageOffset);
            }

            var response = collectionManager.client().scrollAsync(scrollBuilder.build()).get();
            List<UUID> orphanIds = new ArrayList<>();

            for (var point : response.getResultList()) {
                UUID pointUuid = UUID.fromString(point.getId().getUuid());
                if (delegateIndex.containsKey(pointUuid)) {
                    delegateIndex.remove(pointUuid);
                } else {
                    orphanIds.add(pointUuid);
                }
            }

            if (!orphanIds.isEmpty()) {
                var pointIds = orphanIds.stream()
                    .map(PointIdFactory::id)
                    .toList();
                collectionManager.client().deleteAsync(collection, pointIds).get();
                orphansRemoved += orphanIds.size();
            }

            hasMore = response.hasNextPageOffset();
            if (hasMore) {
                nextPageOffset = response.getNextPageOffset();
            }
        }
        return orphansRemoved;
    }
}
```

- [ ] **Step 5: Update QdrantCbrBeanProducer to produce CbrReconciliationService**

Add after the existing `cbrCaseMemoryStore()` producer:

```java
@Produces
@ApplicationScoped
CbrReconciliationService cbrReconciliationService() {
    EmbeddingModel embeddingModel = embeddingModelInstance.isResolvable()
        ? embeddingModelInstance.get() : null;
    CaseMemoryStore delegate = delegateInstance.isResolvable()
        ? delegateInstance.get() : null;

    var collectionManager = new CbrCollectionManager(client(), config);
    return new CbrReconciliationService(collectionManager, embeddingModel, config, delegate);
}
```

Wait — the `client` and `collectionManager` are already created in `cbrCaseMemoryStore()`. We need to share them. Refactor: extract client creation to a shared method, create collectionManager once.

Actually, looking at the current code, `client` is stored as a field and `collectionManager` is created inline. Refactor both producers to share the same client and collection manager:

```java
private CbrCollectionManager collectionManager() {
    if (client == null) {
        var grpcBuilder = QdrantGrpcClient.newBuilder(
            config.host(), config.port(), config.useTls());
        config.apiKey().ifPresent(grpcBuilder::withApiKey);
        client = new QdrantClient(grpcBuilder.build());
    }
    return new CbrCollectionManager(client, config);
}
```

Then update both producers to use `collectionManager()`. Store it as a field if needed for sharing.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -DfailIfNoTests=false`
Expected: ALL PASS.

- [ ] **Step 7: Full build verification**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS across all modules.

- [ ] **Step 8: Commit**

```
feat(#74): CbrReconciliationService — unified single-pass reconciliation with CDI wiring
```

---

## File Map

| File | Action | Task |
|------|--------|------|
| `memory-api/.../cbr/ScoredCbrCase.java` | Modify | 1 |
| `memory-api/.../cbr/CbrCaseTest.java` | Modify | 1 |
| `memory-api/.../MemoryCapability.java` | Modify | 2 |
| `memory-api/.../MemoryScanRequest.java` | Create | 2 |
| `memory-api/.../CaseMemoryStore.java` | Modify | 2 |
| `memory-api/.../CaseMemoryStoreSpiTest.java` | Modify | 2 |
| `memory-api/.../MemoryScanRequestTest.java` | Create | 2 |
| `memory-jpa/.../JpaMemoryStore.java` | Modify | 3 |
| `memory-jpa/.../JpaMemoryStoreTest.java` | Modify | 3 |
| `memory-sqlite/.../SqliteMemoryStore.java` | Modify | 4 |
| `memory-sqlite/.../SqliteMemoryStoreTest.java` | Modify | 4 |
| `memory-qdrant/.../QdrantCbrConfig.java` | Modify | 5 |
| `memory-qdrant/.../CbrDimensionMismatchException.java` | Create | 5 |
| `memory-qdrant/.../CbrCollectionManager.java` | Modify | 5 |
| `memory-qdrant/.../QdrantCbrCaseMemoryStoreTest.java` | Modify | 5 |
| `memory-qdrant/.../CbrAttributeKeys.java` | Create | 6 |
| `memory-qdrant/.../CbrMemorySerializer.java` | Create | 6 |
| `memory-qdrant/.../CbrMemoryDeserializer.java` | Create | 6 |
| `memory-qdrant/.../QdrantCbrCaseMemoryStore.java` | Modify | 6 |
| `memory-qdrant/.../CbrMemoryDeserializerTest.java` | Create | 6 |
| `memory-qdrant/.../ReconciliationResult.java` | Create | 7 |
| `memory-qdrant/.../CbrReconciliationService.java` | Create | 7 |
| `memory-qdrant/.../QdrantCbrBeanProducer.java` | Modify | 7 |
| `memory-qdrant/.../CbrReconciliationServiceTest.java` | Create | 7 |
