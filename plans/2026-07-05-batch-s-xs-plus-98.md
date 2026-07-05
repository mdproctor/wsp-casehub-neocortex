# Batch S/XS + #98 Tenant Discovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use hortora:subagent-driven-development (recommended) or hortora:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 9 issues (#98, #102, #103, #95, #96, #97, #99, #100, #90) on a single branch, covering tenant discovery, batch reconciliation, observability, reactive parity, enrichment SPI, corpus filtering, and ColBERT quantization.

**Architecture:** SPI additions in memory-api form the foundation (discoverTenants, CaseEnrichmentStep, MemoryInput enrichment API, reactive parity). Backend implementations follow. CDI restructuring of CbrReconciliationService enables Micrometer observability and batch reconciliation. Independent changes (corpus hidden paths, ColBERT quantization) have no dependencies.

**Tech Stack:** Java 21, Quarkus 3.32.2, Qdrant, Micrometer, Mutiny, Testcontainers

## Global Constraints

- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`
- Full build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All tests use AssertJ (not JUnit assertions)
- CaseMemoryStore adapters call `MemoryPermissions.assertTenant()` or `assertCrossTenantAdmin()` before backend operations
- Default methods that gate on capabilities throw `MemoryCapabilityException`
- `@DefaultBean` = no-op. Working in-memory = `@Alternative @Priority(N)`.
- Every commit references an issue number

## File Map

### New files
| File | Module | Purpose |
|------|--------|---------|
| `memory-api/.../memory/CaseEnrichmentStep.java` | memory-api | Enrichment SPI |
| `memory/.../memory/runtime/CaseEnrichmentDecorator.java` | memory | @Decorator on CaseMemoryStore |
| `memory/.../memory/runtime/CaseEnrichmentDecoratorTest.java` | memory | Decorator unit test |

### Modified files (by task)
| File | Tasks | Changes |
|------|-------|---------|
| `memory-api/.../memory/MemoryCapability.java` | 3 | Add DISCOVER_TENANTS |
| `memory-api/.../memory/CaseMemoryStore.java` | 3 | Add discoverTenants() |
| `memory-api/.../memory/ReactiveCaseMemoryStore.java` | 3 | Add scan, capabilities, requireCapability, discoverTenants |
| `memory-api/.../memory/MemoryInput.java` | 3 | Add withAttribute, withAttributes |
| `memory/.../runtime/BlockingToReactiveBridge.java` | 4 | Delegate scan, capabilities, requireCapability, discoverTenants |
| `memory-jpa/.../jpa/JpaMemoryStore.java` | 5 | Add discoverTenants() |
| `memory-sqlite/.../sqlite/SqliteMemoryStore.java` | 5 | Add discoverTenants() |
| `memory-inmem/.../inmem/InMemoryMemoryStore.java` | 5 | Add discoverTenants() |
| `corpus/.../zip/FlatCorpusStore.java` | 1 | FileVisitor, hidden path filtering |
| `corpus/.../zip/FlatChangeSource.java` | 1 | Hidden segment filter in onRawEvent |
| `rag/.../runtime/RagConfig.java` | 2 | ColbertQuantizationConfig |
| `rag/.../runtime/QdrantEmbeddingIngestor.java` | 2 | Apply ColBERT quantization |
| `memory-qdrant/.../qdrant/CbrReconciliationService.java` | 7,8,9 | CDI bean, batch upserts, discoverTenants, reconcileAll, @Timed |
| `memory-qdrant/.../qdrant/QdrantCbrBeanProducer.java` | 8 | Produce only CbrCollectionManager |
| `memory-qdrant/.../qdrant/QdrantCbrCaseMemoryStore.java` | 8 | @ApplicationScoped CDI bean |
| `memory-qdrant/.../qdrant/CbrMemoryDeserializer.java` | 7 | Fix control flow (#103-8) |
| `memory-qdrant/pom.xml` | 8 | Add micrometer-core |

---

### Task 1: FlatCorpusStore Hidden Path Filtering (#99)

**Files:**
- Modify: `corpus/src/main/java/io/casehub/neocortex/corpus/zip/FlatCorpusStore.java`
- Modify: `corpus/src/main/java/io/casehub/neocortex/corpus/zip/FlatChangeSource.java`
- Modify: `corpus/src/test/java/io/casehub/neocortex/corpus/zip/FlatCorpusStoreTest.java`
- Modify: `corpus/src/test/java/io/casehub/neocortex/corpus/zip/FlatChangeSourceTest.java`

**Interfaces:**
- Consumes: Nothing — self-contained
- Produces: `FlatCorpusStore.list()` now filters `.`-prefixed path segments; `FlatChangeSource.onRawEvent()` filters hidden segments

- [ ] **Step 1: Write failing tests for FlatCorpusStore hidden path filtering**

Add tests to `FlatCorpusStoreTest.java`:

```java
@Test
void list_excludesHiddenDirectories() throws Exception {
    // Create .git directory structure
    Path gitDir = rootDir.resolve(".git/objects");
    Files.createDirectories(gitDir);
    Files.writeString(gitDir.resolve("abc123"), "blob");

    // Create .DS_Store
    Files.writeString(rootDir.resolve(".DS_Store"), "data");

    // Create normal file
    store.append("visible.txt", "content".getBytes());

    List<String> listed = store.list();
    assertThat(listed).containsExactly("visible.txt");
}

@Test
void list_excludesHiddenFilesInSubdirectories() throws Exception {
    store.append("docs/readme.md", "content".getBytes());
    Path subHidden = rootDir.resolve("docs/.hidden");
    Files.createDirectories(subHidden.getParent());
    Files.writeString(subHidden, "secret");

    List<String> listed = store.list();
    assertThat(listed).containsExactly("docs/readme.md");
}

@Test
void list_preservesUnderscoreSemantics() throws Exception {
    // _prefixed at root level → filtered (existing behavior)
    Files.writeString(rootDir.resolve("_internal.txt"), "meta");
    // _prefixed in subdirectory → NOT filtered (existing behavior)
    store.append("sub/_notes.txt", "notes".getBytes());
    store.append("visible.txt", "content".getBytes());

    List<String> listed = store.list();
    assertThat(listed).containsExactlyInAnyOrder("visible.txt", "sub/_notes.txt");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus -Dtest=FlatCorpusStoreTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: `list_excludesHiddenDirectories` FAILS (`.git/objects/abc123` and `.DS_Store` are listed)

- [ ] **Step 3: Implement FileVisitor in FlatCorpusStore.list()**

Replace the `Files.walk()` stream in `list()` with `Files.walkFileTree()`:

```java
@Override
public List<String> list() {
    List<String> result = new ArrayList<>();
    try {
        Files.walkFileTree(rootDir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                if (dir.equals(rootDir)) return FileVisitResult.CONTINUE;
                if (dir.getFileName().toString().startsWith(".")) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                if (file.getFileName().toString().startsWith(".")) {
                    return FileVisitResult.CONTINUE;
                }
                String relative = rootDir.relativize(file).toString();
                if (!relative.startsWith("_")) {
                    result.add(relative);
                }
                return FileVisitResult.CONTINUE;
            }
        });
    } catch (IOException e) {
        throw new UncheckedIOException("Failed to list files in: " + rootDir, e);
    }
    return result;
}
```

Add imports: `java.nio.file.FileVisitResult`, `java.nio.file.SimpleFileVisitor`, `java.nio.file.attribute.BasicFileAttributes`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus -Dtest=FlatCorpusStoreTest`
Expected: ALL PASS

- [ ] **Step 5: Write failing test for FlatChangeSource hidden path filtering**

Add to `FlatChangeSourceTest.java`:

```java
@Test
void fullScan_excludesHiddenPaths() throws Exception {
    store.append("visible.txt", "content".getBytes());
    Path gitObj = rootDir.resolve(".git/objects/abc");
    Files.createDirectories(gitObj.getParent());
    Files.writeString(gitObj, "blob");

    ChangeSet changes = changeSource.fullScan();
    assertThat(changes.entries()).extracting(ChangedEntry::path)
        .containsExactly("visible.txt");
}
```

- [ ] **Step 6: Verify test passes (fullScan delegates to store.list())**

Since `fullScan()` calls `store.list()` which is already fixed, this test should pass immediately.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus -Dtest=FlatChangeSourceTest`

- [ ] **Step 7: Add hidden segment filter to FlatChangeSource.onRawEvent()**

Add private static method and update `onRawEvent()`:

```java
private static boolean containsHiddenSegment(String relativePath) {
    return relativePath.startsWith(".") || relativePath.contains("/.");
}
```

In `onRawEvent()`, change:
```java
if (relativePath.startsWith("_")) {
```
to:
```java
if (relativePath.startsWith("_") || containsHiddenSegment(relativePath)) {
```

- [ ] **Step 8: Run all corpus tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```
feat(#99): filter hidden paths from FlatCorpusStore.list() and FlatChangeSource

Replace Files.walk() with FileVisitor using SKIP_SUBTREE for dot-prefixed
directories. Add containsHiddenSegment filter to watch events.
```

---

### Task 2: ColBERT Quantization Config (#100)

**Files:**
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/RagConfig.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: existing rag tests if any cover ensureCollection

**Interfaces:**
- Consumes: `DenseQuantization` enum (existing)
- Produces: `RagConfig.colbertQuantization()` config group; `QdrantEmbeddingIngestor.ensureCollection()` applies ColBERT quantization

- [ ] **Step 1: Add ColbertQuantizationConfig to RagConfig**

Add to `RagConfig.java` after the existing `QuantizationConfig quantization();`:

```java
ColbertQuantizationConfig colbertQuantization();

interface ColbertQuantizationConfig {
    @WithDefault("NONE")
    DenseQuantization type();

    @WithDefault("true")
    boolean alwaysRam();
}
```

- [ ] **Step 2: Apply ColBERT quantization in QdrantEmbeddingIngestor.ensureCollection()**

In `ensureCollection()`, replace the ColBERT VectorParams block (around line 283):

```java
if (embedder.supportedModes().contains(EmbeddingMode.COLBERT)) {
    VectorParams.Builder colbertBuilder = VectorParams.newBuilder()
        .setSize(embedder.colbertDimension().orElseThrow())
        .setDistance(Distance.Cosine)
        .setMultivectorConfig(MultiVectorConfig.newBuilder()
            .setComparator(MultiVectorComparator.MaxSim).build());

    if (config.colbertQuantization().type() == DenseQuantization.SCALAR) {
        colbertBuilder.setQuantizationConfig(
            io.qdrant.client.grpc.Collections.QuantizationConfig.newBuilder()
                .setScalar(io.qdrant.client.grpc.Collections.ScalarQuantization.newBuilder()
                    .setType(io.qdrant.client.grpc.Collections.QuantizationType.Int8)
                    .setAlwaysRam(config.colbertQuantization().alwaysRam())
                    .build())
                .build());
    } else if (config.colbertQuantization().type() == DenseQuantization.BINARY) {
        colbertBuilder.setQuantizationConfig(
            io.qdrant.client.grpc.Collections.QuantizationConfig.newBuilder()
                .setBinary(io.qdrant.client.grpc.Collections.BinaryQuantization.newBuilder()
                    .setAlwaysRam(config.colbertQuantization().alwaysRam())
                    .build())
                .build());
    }

    paramsMapBuilder.putMap(config.colbertVectorName(), colbertBuilder.build());
}
```

- [ ] **Step 3: Build rag module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag -DskipTests`
Expected: BUILD SUCCESS (compilation check — config mapping generates correctly)

- [ ] **Step 4: Run rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(#100): ColBERT multi-vector scalar quantization config in RagConfig

Add ColbertQuantizationConfig nested interface reusing DenseQuantization enum.
Apply in QdrantEmbeddingIngestor.ensureCollection() for ColBERT vector params.
```

---

### Task 3: Memory SPI Additions (#98 SPI + #95 SPI + #90 SPI)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryCapability.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/CaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/ReactiveCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/CaseEnrichmentStep.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/MemoryInputTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/CaseMemoryStoreSpiTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/ReactiveCaseMemoryStoreSpiTest.java`

**Interfaces:**
- Consumes: Existing `MemoryCapability`, `CaseMemoryStore`, `ReactiveCaseMemoryStore`, `MemoryInput`
- Produces: `MemoryCapability.DISCOVER_TENANTS`, `CaseMemoryStore.discoverTenants()`, `ReactiveCaseMemoryStore.scan()/.capabilities()/.requireCapability()/.discoverTenants()`, `MemoryInput.withAttribute()/.withAttributes()`, `CaseEnrichmentStep` interface

- [ ] **Step 1: Add DISCOVER_TENANTS to MemoryCapability**

In `MemoryCapability.java`, after `SCAN` (line 29), add:

```java
    DISCOVER_TENANTS
```

- [ ] **Step 2: Add discoverTenants() to CaseMemoryStore**

In `CaseMemoryStore.java`, after the `scan()` method:

```java
/**
 * Returns distinct tenantIds matching the given attribute filter.
 * Both null → all tenants. Both non-null → filtered. Mixed → IllegalArgumentException.
 *
 * <p>Cross-tenant admin operation. Implementations MUST call
 * {@link MemoryPermissions#assertCrossTenantAdmin} before executing.
 *
 * @return a non-null, possibly empty, unmodifiable set of tenant identifiers
 */
default Set<String> discoverTenants(String attributeKey, String attributeValue) {
    if ((attributeKey == null) != (attributeValue == null)) {
        throw new IllegalArgumentException(
            "attributeKey and attributeValue must both be null or both be non-null");
    }
    throw new MemoryCapabilityException(MemoryCapability.DISCOVER_TENANTS, getClass());
}
```

- [ ] **Step 3: Add reactive parity methods to ReactiveCaseMemoryStore**

In `ReactiveCaseMemoryStore.java`, add:

```java
default Uni<List<Memory>> scan(MemoryScanRequest request) {
    return Uni.createFrom().failure(
        new MemoryCapabilityException(MemoryCapability.SCAN, getClass()));
}

default Uni<Set<String>> discoverTenants(String attributeKey, String attributeValue) {
    if ((attributeKey == null) != (attributeValue == null)) {
        return Uni.createFrom().failure(new IllegalArgumentException(
            "attributeKey and attributeValue must both be null or both be non-null"));
    }
    return Uni.createFrom().failure(
        new MemoryCapabilityException(MemoryCapability.DISCOVER_TENANTS, getClass()));
}

default Set<MemoryCapability> capabilities() { return Set.of(); }

default void requireCapability(MemoryCapability capability) {
    if (!capabilities().contains(capability))
        throw new MemoryCapabilityException(capability, getClass());
}
```

Add import: `java.util.Set`

- [ ] **Step 4: Add withAttribute/withAttributes to MemoryInput**

In `MemoryInput.java`, after the compact constructor:

```java
public MemoryInput withAttribute(String key, String value) {
    var merged = new java.util.HashMap<>(attributes);
    merged.put(key, value);
    return new MemoryInput(entityId, domain, tenantId, caseId, text, merged);
}

public MemoryInput withAttributes(Map<String, String> additional) {
    var merged = new java.util.HashMap<>(attributes);
    merged.putAll(additional);
    return new MemoryInput(entityId, domain, tenantId, caseId, text, merged);
}

public MemoryInput withText(String newText) {
    return new MemoryInput(entityId, domain, tenantId, caseId, newText, attributes);
}
```

- [ ] **Step 5: Create CaseEnrichmentStep SPI**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/CaseEnrichmentStep.java`:

```java
package io.casehub.neocortex.memory;

/**
 * SPI for enriching {@link MemoryInput} before storage.
 *
 * <p><b>Progressive routing:</b> {@code appliesTo} and {@code enrich} receive the
 * progressively enriched input — the result of all prior steps (ordered by {@code priority()}),
 * not the original input.
 */
public interface CaseEnrichmentStep {
    boolean appliesTo(MemoryInput input);
    MemoryInput enrich(MemoryInput input);
    default int priority() { return 0; }
    default boolean required() { return false; }
}
```

- [ ] **Step 6: Write tests for MemoryInput.withAttribute**

Add to `MemoryInputTest.java`:

```java
@Test
void withAttribute_addsToExistingAttributes() {
    var input = new MemoryInput("e1", new MemoryDomain("d"), "t1", "c1", "text", Map.of("k1", "v1"));
    var enriched = input.withAttribute("k2", "v2");
    assertThat(enriched.attributes()).containsEntry("k1", "v1").containsEntry("k2", "v2");
    assertThat(enriched.entityId()).isEqualTo("e1");
    assertThat(enriched.text()).isEqualTo("text");
}

@Test
void withAttribute_overwritesExistingKey() {
    var input = new MemoryInput("e1", new MemoryDomain("d"), "t1", "c1", "text", Map.of("k1", "v1"));
    var enriched = input.withAttribute("k1", "v2");
    assertThat(enriched.attributes()).containsEntry("k1", "v2");
}

@Test
void withAttributes_mergesMultiple() {
    var input = new MemoryInput("e1", new MemoryDomain("d"), "t1", "c1", "text", Map.of("k1", "v1"));
    var enriched = input.withAttributes(Map.of("k2", "v2", "k3", "v3"));
    assertThat(enriched.attributes()).hasSize(3);
}

@Test
void withAttribute_preservesImmutability() {
    var input = new MemoryInput("e1", new MemoryDomain("d"), "t1", "c1", "text", Map.of("k1", "v1"));
    var enriched = input.withAttribute("k2", "v2");
    assertThat(input.attributes()).hasSize(1);
    assertThat(enriched.attributes()).hasSize(2);
    assertThatThrownBy(() -> enriched.attributes().put("k3", "v3"))
        .isInstanceOf(UnsupportedOperationException.class);
}

@Test
void withText_replacesText() {
    var input = new MemoryInput("e1", new MemoryDomain("d"), "t1", "c1", "old", Map.of());
    var enriched = input.withText("new");
    assertThat(enriched.text()).isEqualTo("new");
    assertThat(enriched.entityId()).isEqualTo("e1");
}
```

- [ ] **Step 7: Write tests for CaseMemoryStore.discoverTenants default**

Add to `CaseMemoryStoreSpiTest.java`:

```java
@Test
void discoverTenants_defaultThrowsCapabilityException() {
    CaseMemoryStore store = new CaseMemoryStore() {
        @Override public String store(MemoryInput i) { return ""; }
        @Override public List<Memory> query(MemoryQuery q) { return List.of(); }
        @Override public int erase(EraseRequest r) { return 0; }
    };
    assertThatThrownBy(() -> store.discoverTenants("key", "val"))
        .isInstanceOf(MemoryCapabilityException.class);
}

@Test
void discoverTenants_rejectsMixedNullParameters() {
    CaseMemoryStore store = new CaseMemoryStore() {
        @Override public String store(MemoryInput i) { return ""; }
        @Override public List<Memory> query(MemoryQuery q) { return List.of(); }
        @Override public int erase(EraseRequest r) { return 0; }
    };
    assertThatThrownBy(() -> store.discoverTenants("key", null))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> store.discoverTenants(null, "val"))
        .isInstanceOf(IllegalArgumentException.class);
}
```

- [ ] **Step 8: Write tests for ReactiveCaseMemoryStore parity**

Add to `ReactiveCaseMemoryStoreSpiTest.java`:

```java
@Test
void scan_defaultFailsWithCapabilityException() {
    ReactiveCaseMemoryStore store = minimalReactiveStore();
    var request = new MemoryScanRequest("t1", null, null, null, 10, null);
    assertThatThrownBy(() -> store.scan(request).await().indefinitely())
        .isInstanceOf(MemoryCapabilityException.class);
}

@Test
void discoverTenants_defaultFailsWithCapabilityException() {
    ReactiveCaseMemoryStore store = minimalReactiveStore();
    assertThatThrownBy(() -> store.discoverTenants("k", "v").await().indefinitely())
        .isInstanceOf(MemoryCapabilityException.class);
}

@Test
void discoverTenants_rejectsMixedNullParameters() {
    ReactiveCaseMemoryStore store = minimalReactiveStore();
    assertThatThrownBy(() -> store.discoverTenants("k", null).await().indefinitely())
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void capabilities_defaultReturnsEmpty() {
    ReactiveCaseMemoryStore store = minimalReactiveStore();
    assertThat(store.capabilities()).isEmpty();
}

@Test
void requireCapability_throwsWhenMissing() {
    ReactiveCaseMemoryStore store = minimalReactiveStore();
    assertThatThrownBy(() -> store.requireCapability(MemoryCapability.SCAN))
        .isInstanceOf(MemoryCapabilityException.class);
}
```

Where `minimalReactiveStore()` is a helper creating a minimal anonymous implementation with `store`, `query`, `erase`.

- [ ] **Step 9: Run all memory-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```
feat(#98,#95,#90): memory SPI additions — discoverTenants, reactive parity, enrichment step

Add MemoryCapability.DISCOVER_TENANTS, CaseMemoryStore.discoverTenants() with
centralised parameter validation, ReactiveCaseMemoryStore scan/capabilities/
requireCapability/discoverTenants parity, MemoryInput.withAttribute/withAttributes/
withText fluent API, CaseEnrichmentStep SPI with priority and required flags.
```

---

### Task 4: BlockingToReactiveBridge Updates (#95)

**Files:**
- Modify: `memory/src/main/java/io/casehub/memory/runtime/BlockingToReactiveBridge.java`
- Modify: `memory/src/main/java/io/casehub/memory/runtime/NoOpCaseMemoryStore.java` (verify capabilities include DISCOVER_TENANTS handling)

**Interfaces:**
- Consumes: `CaseMemoryStore.scan()`, `.capabilities()`, `.requireCapability()`, `.discoverTenants()` from Task 3
- Produces: `BlockingToReactiveBridge` delegates all four new methods

- [ ] **Step 1: Add bridge methods to BlockingToReactiveBridge**

```java
@Override
public Uni<List<Memory>> scan(MemoryScanRequest request) {
    return Uni.createFrom().item(() -> delegate.scan(request))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}

@Override
public Uni<Set<String>> discoverTenants(String attributeKey, String attributeValue) {
    return Uni.createFrom().item(() -> delegate.discoverTenants(attributeKey, attributeValue))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}

@Override
public Set<MemoryCapability> capabilities() {
    return delegate.capabilities();
}

@Override
public void requireCapability(MemoryCapability capability) {
    delegate.requireCapability(capability);
}
```

Add imports: `io.casehub.neocortex.memory.MemoryScanRequest`, `io.casehub.neocortex.memory.MemoryCapability`, `java.util.Set`

- [ ] **Step 2: Build memory module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```
feat(#95): BlockingToReactiveBridge — delegate scan, capabilities, requireCapability, discoverTenants
```

---

### Task 5: discoverTenants Backend Implementations (#98)

**Files:**
- Modify: `memory-jpa/src/main/java/io/casehub/neocortex/memory/jpa/JpaMemoryStore.java`
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java`
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Modify: `memory-jpa/src/test/java/io/casehub/neocortex/memory/jpa/JpaMemoryStoreTest.java`
- Modify: `memory-sqlite/src/test/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStoreTest.java`

**Interfaces:**
- Consumes: `CaseMemoryStore.discoverTenants()` from Task 3, `MemoryCapability.DISCOVER_TENANTS`
- Produces: Working `discoverTenants()` in JPA, SQLite, InMemory backends

- [ ] **Step 1: Write failing test for JPA discoverTenants**

Add to `JpaMemoryStoreTest.java`:

```java
@Test
void discoverTenants_returnsDistinctTenantIds() {
    store.store(new MemoryInput("e1", domain, "tenant-a", null, "text1", Map.of("cbr.caseType", "game")));
    store.store(new MemoryInput("e2", domain, "tenant-b", null, "text2", Map.of("cbr.caseType", "game")));
    store.store(new MemoryInput("e3", domain, "tenant-a", null, "text3", Map.of("cbr.caseType", "game")));
    store.store(new MemoryInput("e4", domain, "tenant-c", null, "text4", Map.of("cbr.caseType", "other")));

    Set<String> tenants = store.discoverTenants("cbr.caseType", "game");
    assertThat(tenants).containsExactlyInAnyOrder("tenant-a", "tenant-b");
}

@Test
void discoverTenants_allTenantsWhenNoFilter() {
    store.store(new MemoryInput("e1", domain, "tenant-a", null, "text1", Map.of()));
    store.store(new MemoryInput("e2", domain, "tenant-b", null, "text2", Map.of()));

    Set<String> tenants = store.discoverTenants(null, null);
    assertThat(tenants).containsExactlyInAnyOrder("tenant-a", "tenant-b");
}

@Test
void discoverTenants_emptyWhenNoMatch() {
    store.store(new MemoryInput("e1", domain, "tenant-a", null, "text1", Map.of("k", "v")));

    Set<String> tenants = store.discoverTenants("k", "nonexistent");
    assertThat(tenants).isEmpty();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-jpa -Dtest=JpaMemoryStoreTest#discoverTenants_returnsDistinctTenantIds`
Expected: FAIL (MemoryCapabilityException)

- [ ] **Step 3: Implement discoverTenants in JpaMemoryStore**

Follow the `scan()` SQL-building pattern (lines 225-265). Add after `scan()`:

```java
@Timed(value = "casehub.memory.jpa", histogram = true, extraTags = {"operation", "discoverTenants"})
@Override
public Set<String> discoverTenants(String attributeKey, String attributeValue) {
    MemoryPermissions.assertCrossTenantAdmin(principal);

    boolean isH2 = isH2Database();
    StringBuilder sql = new StringBuilder("SELECT DISTINCT m.tenant_id FROM memory_entry m WHERE 1=1");
    Map<String, Object> params = new HashMap<>();

    if (attributeKey != null) {
        if (isH2) {
            String pattern = "%\"" + attributeKey + "\":\"" + attributeValue + "\"%";
            sql.append(" AND m.attributes LIKE :attrPattern");
            params.put("attrPattern", pattern);
        } else {
            sql.append(" AND m.attributes::jsonb->>:attrKey = :attrValue");
            params.put("attrKey", attributeKey);
            params.put("attrValue", attributeValue);
        }
    }

    var query = entityManager.createNativeQuery(sql.toString());
    params.forEach(query::setParameter);

    @SuppressWarnings("unchecked")
    List<String> results = query.getResultList();
    return Set.copyOf(results);
}
```

Add `DISCOVER_TENANTS` to the `capabilities()` set.

- [ ] **Step 4: Run JPA tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-jpa`
Expected: ALL PASS

- [ ] **Step 5: Implement discoverTenants in SqliteMemoryStore**

Follow the `scan()` SQL-building pattern (lines 267-299):

```java
@Timed(value = "casehub.memory.sqlite", histogram = true, extraTags = {"operation", "discoverTenants"})
@Override
public Set<String> discoverTenants(String attributeKey, String attributeValue) {
    MemoryPermissions.assertCrossTenantAdmin(principal);

    StringBuilder sql = new StringBuilder("SELECT DISTINCT tenant_id FROM memory_entry WHERE 1=1");
    List<Object> params = new ArrayList<>();

    if (attributeKey != null) {
        sql.append(" AND json_extract(attributes, ?) = ?");
        params.add("$.\"" + attributeKey + "\"");
        params.add(attributeValue);
    }

    try (Connection conn = dataSource.getConnection();
         PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
        for (int i = 0; i < params.size(); i++) {
            stmt.setObject(i + 1, params.get(i));
        }
        Set<String> tenants = new LinkedHashSet<>();
        try (ResultSet rs = stmt.executeQuery()) {
            while (rs.next()) {
                tenants.add(rs.getString(1));
            }
        }
        return Set.copyOf(tenants);
    } catch (SQLException e) {
        throw new RuntimeException("discoverTenants failed", e);
    }
}
```

Add `DISCOVER_TENANTS` to the `capabilities()` set.

- [ ] **Step 6: Write and run SQLite tests**

Add matching tests to `SqliteMemoryStoreTest.java` (same three test methods as JPA). Run:

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-sqlite`
Expected: ALL PASS

- [ ] **Step 7: Implement discoverTenants in InMemoryMemoryStore**

```java
@Timed(value = "casehub.memory.inmem", histogram = true, extraTags = {"operation", "discoverTenants"})
@Override
public Set<String> discoverTenants(String attributeKey, String attributeValue) {
    return memories.values().stream()
        .filter(m -> attributeKey == null
            || attributeValue.equals(m.attributes().get(attributeKey)))
        .map(Memory::tenantId)
        .collect(Collectors.toUnmodifiableSet());
}
```

Add `DISCOVER_TENANTS` to the `capabilities()` set.

- [ ] **Step 8: Build all backend modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory,memory-jpa,memory-sqlite,memory-inmem`
Expected: BUILD SUCCESS

- [ ] **Step 9: Commit**

```
feat(#98): discoverTenants — JPA, SQLite, InMemory implementations

Cross-tenant admin query for distinct tenantIds, filtered by attribute.
JPA uses PostgreSQL jsonb/H2 LIKE, SQLite uses json_extract, InMemory
uses stream filter. All call assertCrossTenantAdmin before executing.
```

---

### Task 6: CaseEnrichmentDecorator (#90)

**Files:**
- Create: `memory/src/main/java/io/casehub/memory/runtime/CaseEnrichmentDecorator.java`
- Create: `memory/src/test/java/io/casehub/memory/runtime/CaseEnrichmentDecoratorTest.java`

**Interfaces:**
- Consumes: `CaseEnrichmentStep` from Task 3, `CaseMemoryStore`
- Produces: `@Decorator` on `CaseMemoryStore` that applies enrichment before `store()` and `storeAll()`

- [ ] **Step 1: Write failing test for enrichment decorator**

Create `CaseEnrichmentDecoratorTest.java`:

```java
package io.casehub.memory.runtime;

import io.casehub.neocortex.memory.*;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class CaseEnrichmentDecoratorTest {

    private static final MemoryDomain DOMAIN = new MemoryDomain("test");

    @Test
    void store_appliesEnrichmentBeforeDelegating() {
        var delegate = new RecordingStore();
        var step = new TestStep("enriched", "value");
        var decorator = new CaseEnrichmentDecorator(delegate, List.of(step));

        var input = new MemoryInput("e1", DOMAIN, "t1", null, "text", Map.of());
        decorator.store(input);

        assertThat(delegate.lastInput.attributes()).containsEntry("enriched", "value");
    }

    @Test
    void store_appliesStepsInPriorityOrder() {
        var delegate = new RecordingStore();
        var stepB = new TestStep("order", "B") { @Override public int priority() { return 10; } };
        var stepA = new TestStep("order", "A") { @Override public int priority() { return 1; } };
        var decorator = new CaseEnrichmentDecorator(delegate, List.of(stepB, stepA));

        decorator.store(new MemoryInput("e1", DOMAIN, "t1", null, "text", Map.of()));

        assertThat(delegate.lastInput.attributes().get("order")).isEqualTo("B");
    }

    @Test
    void store_optionalStepFailureDoesNotPreventStore() {
        var delegate = new RecordingStore();
        var failingStep = new CaseEnrichmentStep() {
            @Override public boolean appliesTo(MemoryInput i) { return true; }
            @Override public MemoryInput enrich(MemoryInput i) { throw new RuntimeException("boom"); }
        };
        var decorator = new CaseEnrichmentDecorator(delegate, List.of(failingStep));

        decorator.store(new MemoryInput("e1", DOMAIN, "t1", null, "text", Map.of()));
        assertThat(delegate.lastInput).isNotNull();
    }

    @Test
    void store_requiredStepFailurePreventsStore() {
        var delegate = new RecordingStore();
        var requiredStep = new CaseEnrichmentStep() {
            @Override public boolean appliesTo(MemoryInput i) { return true; }
            @Override public MemoryInput enrich(MemoryInput i) { throw new RuntimeException("required failure"); }
            @Override public boolean required() { return true; }
        };
        var decorator = new CaseEnrichmentDecorator(delegate, List.of(requiredStep));

        assertThatThrownBy(() -> decorator.store(
            new MemoryInput("e1", DOMAIN, "t1", null, "text", Map.of())))
            .isInstanceOf(RuntimeException.class)
            .hasMessageContaining("required failure");
        assertThat(delegate.lastInput).isNull();
    }

    @Test
    void store_stepThatDoesNotApplyIsSkipped() {
        var delegate = new RecordingStore();
        var step = new CaseEnrichmentStep() {
            @Override public boolean appliesTo(MemoryInput i) { return false; }
            @Override public MemoryInput enrich(MemoryInput i) { return i.withAttribute("applied", "true"); }
        };
        var decorator = new CaseEnrichmentDecorator(delegate, List.of(step));

        decorator.store(new MemoryInput("e1", DOMAIN, "t1", null, "text", Map.of()));
        assertThat(delegate.lastInput.attributes()).doesNotContainKey("applied");
    }

    @Test
    void query_delegatesDirectly() {
        var delegate = new RecordingStore();
        var decorator = new CaseEnrichmentDecorator(delegate, List.of());
        decorator.query(new MemoryQuery("e1", DOMAIN, "t1", null, null, null, 10));
        assertThat(delegate.queryCalled).isTrue();
    }

    static class RecordingStore implements CaseMemoryStore {
        MemoryInput lastInput;
        boolean queryCalled;
        @Override public String store(MemoryInput i) { lastInput = i; return "id"; }
        @Override public List<Memory> query(MemoryQuery q) { queryCalled = true; return List.of(); }
        @Override public int erase(EraseRequest r) { return 0; }
    }

    static class TestStep implements CaseEnrichmentStep {
        private final String key, value;
        TestStep(String key, String value) { this.key = key; this.value = value; }
        @Override public boolean appliesTo(MemoryInput i) { return true; }
        @Override public MemoryInput enrich(MemoryInput i) { return i.withAttribute(key, value); }
    }
}
```

- [ ] **Step 2: Run test to verify it fails (class not found)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=CaseEnrichmentDecoratorTest`
Expected: COMPILATION ERROR (CaseEnrichmentDecorator does not exist)

- [ ] **Step 3: Create CaseEnrichmentDecorator**

Create `memory/src/main/java/io/casehub/memory/runtime/CaseEnrichmentDecorator.java`:

```java
package io.casehub.memory.runtime;

import io.casehub.neocortex.memory.*;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;

@Decorator
@Priority(jakarta.interceptor.Interceptor.Priority.APPLICATION)
public class CaseEnrichmentDecorator implements CaseMemoryStore {

    private static final Logger LOG = Logger.getLogger(CaseEnrichmentDecorator.class.getName());

    private final CaseMemoryStore delegate;
    private final List<CaseEnrichmentStep> sortedSteps;

    @Inject
    CaseEnrichmentDecorator(@Delegate @Any CaseMemoryStore delegate,
                            Instance<CaseEnrichmentStep> steps) {
        this.delegate = delegate;
        this.sortedSteps = steps.stream()
            .sorted(Comparator.comparingInt(CaseEnrichmentStep::priority))
            .toList();
    }

    CaseEnrichmentDecorator(CaseMemoryStore delegate, List<CaseEnrichmentStep> sortedSteps) {
        this.delegate = delegate;
        this.sortedSteps = sortedSteps;
    }

    @Override
    public String store(MemoryInput input) {
        return delegate.store(applyEnrichment(input));
    }

    @Override
    public StoreAllResult storeAll(List<MemoryInput> inputs) {
        return delegate.storeAll(inputs.stream().map(this::applyEnrichment).toList());
    }

    @Override public List<Memory> query(MemoryQuery q) { return delegate.query(q); }
    @Override public int erase(EraseRequest r) { return delegate.erase(r); }
    @Override public int eraseEntity(String entityId, String tenantId) { return delegate.eraseEntity(entityId, tenantId); }
    @Override public void eraseById(String memoryId, String entityId, String tenantId) { delegate.eraseById(memoryId, entityId, tenantId); }
    @Override public int eraseEntityAcrossTenants(String entityId, Set<String> tenantIds) { return delegate.eraseEntityAcrossTenants(entityId, tenantIds); }
    @Override public Set<MemoryCapability> capabilities() { return delegate.capabilities(); }
    @Override public void requireCapability(MemoryCapability cap) { delegate.requireCapability(cap); }
    @Override public List<Memory> scan(MemoryScanRequest request) { return delegate.scan(request); }
    @Override public Set<String> discoverTenants(String attributeKey, String attributeValue) { return delegate.discoverTenants(attributeKey, attributeValue); }

    private MemoryInput applyEnrichment(MemoryInput input) {
        if (sortedSteps.isEmpty()) return input;
        MemoryInput result = input;
        for (CaseEnrichmentStep step : sortedSteps) {
            if (step.appliesTo(result)) {
                try {
                    result = step.enrich(result);
                } catch (Exception e) {
                    if (step.required()) {
                        if (e instanceof RuntimeException re) throw re;
                        throw new RuntimeException("Required enrichment step failed: " + step.getClass().getName(), e);
                    }
                    LOG.log(Level.WARNING, "Enrichment step " + step.getClass().getName() + " failed", e);
                }
            }
        }
        return result;
    }
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=CaseEnrichmentDecoratorTest`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(#90): CaseEnrichmentDecorator — pre-store enrichment pipeline

@Decorator on CaseMemoryStore in memory/ module. Applies CaseEnrichmentStep
instances in priority order. Required steps propagate failures; optional
steps log and continue. Progressive routing documented.
```

---

### Task 7: Minor Review Findings (#103)

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrMemoryDeserializer.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationService.java` (imports only)
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationServiceTest.java`
- Modify: `memory-jpa/src/test/java/io/casehub/neocortex/memory/jpa/JpaMemoryStoreTest.java` (JUnit→AssertJ)

**Interfaces:**
- Consumes: Existing classes
- Produces: Cleaner code, better test coverage

- [ ] **Step 1: Fix CbrMemoryDeserializer control flow (#103-8)**

In `CbrMemoryDeserializer.java`, change `parseFeatures` and `parsePlanTrace` to return null on parse failure instead of throwing:

```java
private static Map<String, Object> parseFeatures(Map<String, String> attrs) {
    String json = attrs.get(CbrAttributeKeys.CBR_FEATURES);
    if (json == null) return Map.of();
    try {
        return MAPPER.readValue(json, MAP_TYPE);
    } catch (JsonProcessingException e) {
        LOG.warning("Malformed cbr.features JSON: " + e.getMessage());
        return null;
    }
}

private static List<PlanTrace> parsePlanTrace(Map<String, String> attrs) {
    String json = attrs.get(CbrAttributeKeys.CBR_PLAN_TRACE);
    if (json == null) return List.of();
    try {
        return MAPPER.readValue(json, PLAN_TRACE_TYPE);
    } catch (JsonProcessingException e) {
        LOG.warning("Malformed cbr.planTrace JSON: " + e.getMessage());
        return null;
    }
}
```

Update the switch cases to check for null:

```java
case FeatureVectorCbrCase.CBR_TYPE -> {
    Map<String, Object> features = parseFeatures(attrs);
    if (features == null) yield null;
    yield new FeatureVectorCbrCase(problem, solution, outcome, confidence, features);
}
case PlanCbrCase.CBR_TYPE -> {
    Map<String, Object> features = parseFeatures(attrs);
    if (features == null) yield null;
    List<PlanTrace> planTrace = parsePlanTrace(attrs);
    if (planTrace == null) yield null;
    yield new PlanCbrCase(problem, solution, outcome, confidence, features, planTrace);
}
```

- [ ] **Step 2: Fix imports in CbrReconciliationService (#103-7)**

Replace fully-qualified `io.qdrant.client.grpc.Common.Filter` and `io.qdrant.client.grpc.Common.PointId` with imports. Add:

```java
import io.qdrant.client.grpc.Common.Filter;
import io.qdrant.client.grpc.Common.PointId;
```

Update all usages in the file from `io.qdrant.client.grpc.Common.Filter` to `Filter` and `io.qdrant.client.grpc.Common.PointId` to `PointId`.

- [ ] **Step 3: Fix CbrReconciliationServiceTest — add @AfterEach, error counter test, AssertJ**

Add `@AfterEach` to close QdrantClient:

```java
@AfterEach
void tearDown() {
    if (collectionManager != null) {
        try { collectionManager.client().close(); } catch (Exception ignored) {}
    }
}
```

Add error-counting test:

```java
@Test
void reconcile_deserializationFailure_incrementsErrorCount() {
    // Store a memory directly in delegate with missing 'solution' attribute
    delegate.storeRaw("case-err", ENTITY, CBR, TENANT,
        "text", Map.of(CbrAttributeKeys.CBR_CASE_TYPE, "err-type",
                       CbrAttributeKeys.CBR_TYPE, FeatureVectorCbrCase.CBR_TYPE));
    // Missing solution → CbrMemoryDeserializer returns empty

    var result = reconciler.reconcile("err-type", TENANT);
    assertThat(result.errors()).isEqualTo(1);
    assertThat(result.entriesReindexed()).isZero();
}
```

Add `storeRaw` helper to `InMemoryDelegateStore` for raw Memory insertion (bypassing CbrMemorySerializer).

Convert any JUnit assertions in scan tests to AssertJ (#103-2).

Add NEGATIVE_INFINITY boundary test for ScoredCbrCase (#103-1) — add as a test in the existing ScoredCbrCase test file or create one.

- [ ] **Step 4: Run memory-qdrant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
chore(#103): minor review findings — deserializer control flow, imports, test coverage

Fix CbrMemoryDeserializer to return null on parse failure instead of throwing
RuntimeException. Clean up fully-qualified Qdrant imports. Add @AfterEach
cleanup, error-counting test, NEGATIVE_INFINITY boundary test. Convert JUnit
assertions to AssertJ.
```

---

### Task 8: CDI Restructuring + Batch Upserts (#96 prereq + #102)

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrBeanProducer.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationService.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/pom.xml`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationServiceTest.java`

**Interfaces:**
- Consumes: `CbrCollectionManager`, `Instance<EmbeddingModel>`, `Instance<CaseMemoryStore>`, `QdrantCbrConfig`
- Produces: CDI-managed `CbrReconciliationService` and `QdrantCbrCaseMemoryStore`, chunked batch upserts

- [ ] **Step 1: Add micrometer-core to memory-qdrant/pom.xml**

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-core</artifactId>
</dependency>
```

- [ ] **Step 2: Restructure QdrantCbrBeanProducer**

Keep only `CbrCollectionManager` production and `QdrantClient` lifecycle:

```java
@ApplicationScoped
public class QdrantCbrBeanProducer {

    private final QdrantCbrConfig config;
    private volatile QdrantClient client;

    @Inject
    public QdrantCbrBeanProducer(QdrantCbrConfig config) {
        this.config = config;
    }

    @Produces
    @ApplicationScoped
    CbrCollectionManager cbrCollectionManager() {
        var grpcBuilder = QdrantGrpcClient.newBuilder(
            config.host(), config.port(), config.useTls());
        config.apiKey().ifPresent(grpcBuilder::withApiKey);
        client = new QdrantClient(grpcBuilder.build());
        return new CbrCollectionManager(client, config);
    }

    @PreDestroy
    void close() {
        if (client != null) {
            try { client.close(); } catch (Exception ignored) {}
        }
    }
}
```

- [ ] **Step 3: Make QdrantCbrCaseMemoryStore a CDI bean**

Add `@ApplicationScoped` and `@Inject` constructor:

```java
@ApplicationScoped
public class QdrantCbrCaseMemoryStore implements CbrCaseMemoryStore {
    // ...

    @Inject
    QdrantCbrCaseMemoryStore(CbrCollectionManager collectionManager,
                              Instance<EmbeddingModel> embeddingModelInstance,
                              QdrantCbrConfig config,
                              Instance<CaseMemoryStore> delegateInstance) {
        this.collectionManager = collectionManager;
        this.embeddingModel = embeddingModelInstance.isResolvable() ? embeddingModelInstance.get() : null;
        this.config = config;
        this.delegate = delegateInstance.isResolvable() ? delegateInstance.get() : null;
    }

    // Keep existing package-private constructor for tests
    QdrantCbrCaseMemoryStore(CbrCollectionManager collectionManager,
                              EmbeddingModel embeddingModel,
                              QdrantCbrConfig config,
                              CaseMemoryStore delegate) { /* existing */ }
```

- [ ] **Step 4: Make CbrReconciliationService a CDI bean with batch upserts**

Add `@ApplicationScoped`, `@Inject` constructor, and chunk the upsert:

```java
@ApplicationScoped
public class CbrReconciliationService {

    private static final Logger LOG = Logger.getLogger(CbrReconciliationService.class.getName());
    private static final int DEFAULT_PAGE_SIZE = 100;

    private final CbrCollectionManager collectionManager;
    private final EmbeddingModel embeddingModel;
    private final QdrantCbrConfig config;
    private final CaseMemoryStore delegate;

    @Inject
    CbrReconciliationService(CbrCollectionManager collectionManager,
                              Instance<EmbeddingModel> embeddingModelInstance,
                              QdrantCbrConfig config,
                              Instance<CaseMemoryStore> delegateInstance) {
        this.collectionManager = collectionManager;
        this.embeddingModel = embeddingModelInstance.isResolvable() ? embeddingModelInstance.get() : null;
        this.config = config;
        this.delegate = delegateInstance.isResolvable() ? delegateInstance.get() : null;
    }

    CbrReconciliationService(CbrCollectionManager collectionManager,
                              EmbeddingModel embeddingModel,
                              QdrantCbrConfig config,
                              CaseMemoryStore delegate) {
        this.collectionManager = collectionManager;
        this.embeddingModel = embeddingModel;
        this.config = config;
        this.delegate = delegate;
    }
```

In `reconcile()`, replace the single-batch upsert with chunked batches:

```java
// Step 3: Reindex remaining (missing from Qdrant)
int reindexed = 0;
int errors = 0;
if (!delegateIndex.isEmpty()) {
    int vectorDim = embeddingModel != null ? embeddingModel.dimension() : 0;
    collectionManager.ensureCollection(caseType, vectorDim);

    List<PointStruct> batch = new ArrayList<>();
    for (var entry : delegateIndex.entrySet()) {
        try {
            // ... existing point building code ...
            batch.add(point);
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to reindex memory " + entry.getValue().memoryId(), e);
            errors++;
        }
    }
    if (!batch.isEmpty()) {
        try {
            for (int i = 0; i < batch.size(); i += DEFAULT_PAGE_SIZE) {
                List<PointStruct> chunk = batch.subList(i, Math.min(i + DEFAULT_PAGE_SIZE, batch.size()));
                collectionManager.client().upsertAsync(collection, chunk).get();
                reindexed += chunk.size();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted during batch upsert", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Batch upsert failed", e.getCause());
        }
    }
}
```

- [ ] **Step 5: Update tests for new constructors**

The test `setUp()` uses the package-private constructors, which still work. Verify:

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```
refactor(#96,#102): CDI restructure CbrReconciliationService + batch upserts

Make CbrReconciliationService and QdrantCbrCaseMemoryStore @ApplicationScoped
CDI beans with @Inject constructors. QdrantCbrBeanProducer now produces only
CbrCollectionManager. Chunk upserts by DEFAULT_PAGE_SIZE with reindexed counter
after confirmed upsert.
```

---

### Task 9: Tenant Discovery + Batch Reconciliation + Observability (#98 + #97 + #96)

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationService.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationServiceTest.java`

**Interfaces:**
- Consumes: `CaseMemoryStore.discoverTenants()` from Task 5, CDI restructuring from Task 8, `MeterRegistry`
- Produces: `CbrReconciliationService.discoverTenants(caseType)`, `.reconcileAll(caseType, tenantIds)`, `.reconcileAll(caseType)`, `@Timed` on reconcile methods, Micrometer counters

- [ ] **Step 1: Write failing test for discoverTenants**

Add to `CbrReconciliationServiceTest.java`:

```java
@Test
void discoverTenants_returnsTenantsFromDelegate() {
    cbrStore.registerSchema(CbrFeatureSchema.of("disc-type", FeatureField.categorical("cat")));
    cbrStore.store(new FeatureVectorCbrCase("p1", "s1", null, null,
        Map.of("cat", "A")), "disc-type", ENTITY, CBR, "tenant-x", "case-1");
    cbrStore.store(new FeatureVectorCbrCase("p2", "s2", null, null,
        Map.of("cat", "B")), "disc-type", ENTITY, CBR, "tenant-y", "case-2");

    Set<String> tenants = reconciler.discoverTenants("disc-type");
    assertThat(tenants).containsExactlyInAnyOrder("tenant-x", "tenant-y");
}

@Test
void discoverTenants_noDelegate_throwsIllegalState() {
    var noDelegate = new CbrReconciliationService(collectionManager, null, config, null);
    assertThatThrownBy(() -> noDelegate.discoverTenants("type"))
        .isInstanceOf(IllegalStateException.class);
}
```

- [ ] **Step 2: Implement discoverTenants on CbrReconciliationService**

```java
public Set<String> discoverTenants(String caseType) {
    if (delegate == null) {
        throw new IllegalStateException("No delegate configured — tenant discovery unavailable");
    }
    delegate.requireCapability(MemoryCapability.DISCOVER_TENANTS);
    return delegate.discoverTenants(CbrAttributeKeys.CBR_CASE_TYPE, caseType);
}
```

- [ ] **Step 3: Write failing test for reconcileAll**

```java
@Test
void reconcileAll_reconcilesMultipleTenants() {
    cbrStore.registerSchema(CbrFeatureSchema.of("multi-type", FeatureField.categorical("cat")));
    cbrStore.store(new FeatureVectorCbrCase("p1", "s1", null, null,
        Map.of("cat", "A")), "multi-type", ENTITY, CBR, "t1", "case-1");
    cbrStore.store(new FeatureVectorCbrCase("p2", "s2", null, null,
        Map.of("cat", "B")), "multi-type", ENTITY, CBR, "t2", "case-2");

    // Delete collection to force reindex
    String collection = collectionManager.collectionName("multi-type");
    try { collectionManager.client().deleteCollectionAsync(collection).get(); } catch (Exception e) { throw new RuntimeException(e); }

    var results = reconciler.reconcileAll("multi-type", Set.of("t1", "t2"));
    assertThat(results).hasSize(2);
    assertThat(results).allMatch(r -> r.entriesReindexed() > 0 || r.errors() == 0);
}
```

- [ ] **Step 4: Implement reconcileAll methods**

```java
public List<ReconciliationResult> reconcileAll(String caseType, Set<String> tenantIds) {
    List<ReconciliationResult> results = new ArrayList<>();
    for (String tenantId : tenantIds) {
        try {
            results.add(reconcile(caseType, tenantId));
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Reconciliation failed for tenant " + tenantId, e);
            results.add(new ReconciliationResult(caseType, tenantId, 0, 0, 1));
        }
    }
    return results;
}

public List<ReconciliationResult> reconcileAll(String caseType) {
    Set<String> tenants = discoverTenants(caseType);
    if (tenants.isEmpty()) {
        LOG.info("No tenants discovered for caseType=" + caseType);
        return List.of();
    }
    return reconcileAll(caseType, tenants);
}
```

- [ ] **Step 5: Add @Timed and Micrometer counters**

Add `MeterRegistry` to the `@Inject` constructor (and keep it nullable in the test constructor):

```java
private final MeterRegistry meterRegistry; // nullable in tests

@Inject
CbrReconciliationService(CbrCollectionManager collectionManager,
                          Instance<EmbeddingModel> embeddingModelInstance,
                          QdrantCbrConfig config,
                          Instance<CaseMemoryStore> delegateInstance,
                          MeterRegistry meterRegistry) {
    // ...
    this.meterRegistry = meterRegistry;
}
```

Add `@Timed` annotations:

```java
@Timed(value = "casehub.cbr.reconciliation", histogram = true,
       extraTags = {"operation", "reconcile"})
public ReconciliationResult reconcile(String caseType, String tenantId) { ... }

@Timed(value = "casehub.cbr.reconciliation", histogram = true,
       extraTags = {"operation", "reconcileAll"})
public List<ReconciliationResult> reconcileAll(String caseType, Set<String> tenantIds) { ... }
```

At the end of `reconcile()`, before returning the result, add counters:

```java
if (meterRegistry != null) {
    meterRegistry.counter("casehub.cbr.reconciliation.orphans", "caseType", caseType).increment(orphansRemoved);
    meterRegistry.counter("casehub.cbr.reconciliation.reindexed", "caseType", caseType).increment(reindexed);
    meterRegistry.counter("casehub.cbr.reconciliation.errors", "caseType", caseType).increment(errors);
}
```

Import: `io.micrometer.core.annotation.Timed`, `io.micrometer.core.instrument.MeterRegistry`

- [ ] **Step 6: Update InMemoryDelegateStore in test to support discoverTenants**

Add to `InMemoryDelegateStore`:

```java
@Override
public Set<MemoryCapability> capabilities() {
    return Set.of(MemoryCapability.SCAN, MemoryCapability.DISCOVER_TENANTS);
}

@Override
public Set<String> discoverTenants(String attributeKey, String attributeValue) {
    return entries.stream()
        .filter(m -> attributeKey == null
            || attributeValue.equals(m.attributes().get(attributeKey)))
        .map(Memory::tenantId)
        .collect(java.util.stream.Collectors.toUnmodifiableSet());
}
```

- [ ] **Step 7: Run all memory-qdrant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```
feat(#98,#97,#96): tenant discovery, batch reconciliation, Micrometer observability

Add discoverTenants(caseType) on CbrReconciliationService — delegates to
CaseMemoryStore.discoverTenants. Add reconcileAll overloads for explicit
tenant set and auto-discovery. Add @Timed and programmatic counters for
orphans/reindexed/errors.
```

---

## Final Verification

- [ ] **Full build**: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- [ ] **All modules pass**: Verify no cross-module compilation or test failures
- [ ] **Review**: Invoke `superpowers:requesting-code-review`
- [ ] **Doc sync**: Invoke `implementation-doc-sync`
