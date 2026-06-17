# Hortora Integration Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `rag/` modules consumable by Hortora by making `CurrentPrincipal` tenancy checks optional via a `TenantGuard` strategy, and update ARC42STORIES to reflect the boundary shift.

**Architecture:** `TenantGuard` is a `@FunctionalInterface` strategy constructed once at CDI producer time. It replaces the `CurrentPrincipal` field in all four `rag/` implementation classes. When `CurrentPrincipal` is provided (casehub), `TenantGuard` delegates to `MemoryPermissions.assertTenant()`. When absent (Hortora), it no-ops. Implementation constructors become package-private to enforce CDI injection.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI `Instance<>`, casehub-platform-api `MemoryPermissions`

**Spec:** `specs/2026-06-17-hortora-integration-gaps-design.md`
**Issue:** casehubio/neural-text#36

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
**Build single module:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`
**Run single test:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl <module> -Dtest=<TestClass>#<method>`

---

### Task 1: TenantGuard interface + unit test

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/TenantGuard.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/TenantGuardTest.java`

- [ ] **Step 1: Write failing tests for TenantGuard**

```java
package io.casehub.rag.runtime;

import io.casehub.platform.api.identity.CurrentPrincipal;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.*;

class TenantGuardTest {

    @Test
    void nullPrincipalProducesNoOpGuard() {
        TenantGuard guard = TenantGuard.of(null);
        assertThatCode(() -> guard.assertTenant("any-tenant"))
            .doesNotThrowAnyException();
    }

    @Test
    void matchingTenantPasses() {
        CurrentPrincipal principal = stubPrincipal("tenant-1");
        TenantGuard guard = TenantGuard.of(principal);
        assertThatCode(() -> guard.assertTenant("tenant-1"))
            .doesNotThrowAnyException();
    }

    @Test
    void mismatchedTenantThrows() {
        CurrentPrincipal principal = stubPrincipal("tenant-1");
        TenantGuard guard = TenantGuard.of(principal);
        assertThatThrownBy(() -> guard.assertTenant("tenant-2"))
            .isInstanceOf(SecurityException.class);
    }

    private static CurrentPrincipal stubPrincipal(String tenantId) {
        return new CurrentPrincipal() {
            @Override public String actorId() { return "test"; }
            @Override public Set<String> groups() { return Set.of(); }
            @Override public String tenancyId() { return tenantId; }
            @Override public boolean isCrossTenantAdmin() { return false; }
        };
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=TenantGuardTest`
Expected: FAIL — `TenantGuard` does not exist

- [ ] **Step 3: Implement TenantGuard**

```java
package io.casehub.rag.runtime;

import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;

@FunctionalInterface
interface TenantGuard {

    void assertTenant(String tenantId);

    static TenantGuard of(CurrentPrincipal principal) {
        return principal == null
            ? tenantId -> {}
            : tenantId -> MemoryPermissions.assertTenant(
                tenantId, principal, RequestContextCheck.isActive());
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=TenantGuardTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/TenantGuard.java rag/src/test/java/io/casehub/rag/runtime/TenantGuardTest.java
git commit -m "feat(#36): add TenantGuard strategy — deployment-time tenancy policy"
```

---

### Task 2: QdrantEmbeddingIngestor — replace CurrentPrincipal with TenantGuard

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`

- [ ] **Step 1: Replace CurrentPrincipal field and constructor parameter with TenantGuard**

In `QdrantEmbeddingIngestor.java`, make these changes:

Remove the import:
```java
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
```

Change the field (line 52):
```java
// Before
private final CurrentPrincipal currentPrincipal;

// After
private final TenantGuard tenantGuard;
```

Change the constructor visibility from `public` to package-private, and change the parameter (line 56):
```java
// Before
public QdrantEmbeddingIngestor(
        QdrantClient client,
        EmbeddingModel embeddingModel,
        SparseEmbedder sparseEmbedder,
        TenancyStrategy tenancyStrategy,
        String denseVectorName,
        String sparseVectorName,
        CurrentPrincipal currentPrincipal) {

// After
QdrantEmbeddingIngestor(
        QdrantClient client,
        EmbeddingModel embeddingModel,
        SparseEmbedder sparseEmbedder,
        TenancyStrategy tenancyStrategy,
        String denseVectorName,
        String sparseVectorName,
        TenantGuard tenantGuard) {
```

Update the field assignment:
```java
// Before
this.currentPrincipal = currentPrincipal;

// After
this.tenantGuard = tenantGuard;
```

- [ ] **Step 2: Replace all 4 assertTenant call sites**

Replace each `MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal, RequestContextCheck.isActive());` with:

```java
tenantGuard.assertTenant(corpus.tenantId());
```

The 4 call sites are in: `ingest()`, `deleteDocument()`, `deleteCorpus()`, `listDocuments()`.

- [ ] **Step 3: Verify rag module compiles (tests will fail — expected, fixed in Task 6)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`
Expected: PASS (compilation succeeds; tests not run)

- [ ] **Step 4: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java
git commit -m "feat(#36): QdrantEmbeddingIngestor — TenantGuard replaces CurrentPrincipal"
```

---

### Task 3: HybridCaseRetriever — replace CurrentPrincipal with TenantGuard

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`

- [ ] **Step 1: Replace CurrentPrincipal field, constructor, and assertTenant call**

Remove the imports:
```java
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
```

Change the field (line 51):
```java
// Before
private final CurrentPrincipal currentPrincipal;

// After
private final TenantGuard tenantGuard;
```

Change constructor visibility from `public` to package-private, change last parameter:
```java
// Before
public HybridCaseRetriever(
        ...
        CurrentPrincipal currentPrincipal) {

// After
HybridCaseRetriever(
        ...
        TenantGuard tenantGuard) {
```

Update field assignment:
```java
// Before
this.currentPrincipal = currentPrincipal;

// After
this.tenantGuard = tenantGuard;
```

Replace the 1 assertTenant call site in `retrieve()`:
```java
// Before
MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal, RequestContextCheck.isActive());

// After
tenantGuard.assertTenant(corpus.tenantId());
```

- [ ] **Step 2: Verify rag module compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java
git commit -m "feat(#36): HybridCaseRetriever — TenantGuard replaces CurrentPrincipal"
```

---

### Task 4: ReactiveQdrantEmbeddingIngestor — replace CurrentPrincipal with TenantGuard

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`

- [ ] **Step 1: Replace CurrentPrincipal field, constructor, and 4 assertTenant calls**

Remove the imports:
```java
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
```

Change the field:
```java
// Before
private final CurrentPrincipal currentPrincipal;

// After
private final TenantGuard tenantGuard;
```

Change constructor visibility from `public` to package-private, change last parameter:
```java
// Before
public ReactiveQdrantEmbeddingIngestor(
        ...
        CurrentPrincipal currentPrincipal) {

// After
ReactiveQdrantEmbeddingIngestor(
        ...
        TenantGuard tenantGuard) {
```

Update field assignment:
```java
// Before
this.currentPrincipal = currentPrincipal;

// After
this.tenantGuard = tenantGuard;
```

Replace all 4 assertTenant call sites (`ingest()`, `deleteDocument()`, `deleteCorpus()`, `listDocuments()`):
```java
// Before (each occurrence)
MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal, RequestContextCheck.isActive());

// After (each occurrence)
tenantGuard.assertTenant(corpus.tenantId());
```

- [ ] **Step 2: Verify rag module compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java
git commit -m "feat(#36): ReactiveQdrantEmbeddingIngestor — TenantGuard replaces CurrentPrincipal"
```

---

### Task 5: ReactiveHybridCaseRetriever — replace CurrentPrincipal with TenantGuard

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`

- [ ] **Step 1: Replace CurrentPrincipal field, constructor, and assertTenant call**

Remove the imports:
```java
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
```

Change the field:
```java
// Before
private final CurrentPrincipal currentPrincipal;

// After
private final TenantGuard tenantGuard;
```

Change constructor visibility from `public` to package-private, change last parameter:
```java
// Before
public ReactiveHybridCaseRetriever(
        ...
        CurrentPrincipal currentPrincipal) {

// After
ReactiveHybridCaseRetriever(
        ...
        TenantGuard tenantGuard) {
```

Update field assignment:
```java
// Before
this.currentPrincipal = currentPrincipal;

// After
this.tenantGuard = tenantGuard;
```

Replace the 1 assertTenant call site in `retrieve()`:
```java
// Before
MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal, RequestContextCheck.isActive());

// After
tenantGuard.assertTenant(corpus.tenantId());
```

- [ ] **Step 2: Verify rag module compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java
git commit -m "feat(#36): ReactiveHybridCaseRetriever — TenantGuard replaces CurrentPrincipal"
```

---

### Task 6: Bean producers — Instance<CurrentPrincipal> + TenantGuard construction

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java`

- [ ] **Step 1: Update RagBeanProducer**

Change the injection:
```java
// Before
@Inject CurrentPrincipal currentPrincipal;

// After
@Inject Instance<CurrentPrincipal> currentPrincipalInstance;
```

Update `corpusStore()`:
```java
@Produces
@ApplicationScoped
QdrantEmbeddingIngestor corpusStore() {
    SparseEmbedder sparseEmbedder = sparseEmbedderInstance.isResolvable()
        ? sparseEmbedderInstance.get() : null;
    CurrentPrincipal principal = currentPrincipalInstance.isResolvable()
        ? currentPrincipalInstance.get() : null;
    TenantGuard tenantGuard = TenantGuard.of(principal);
    return new QdrantEmbeddingIngestor(
        client,
        embeddingModel,
        sparseEmbedder,
        config.tenancyStrategy(),
        config.denseVectorName(),
        config.sparseVectorName(),
        tenantGuard);
}
```

Update `caseRetriever()`:
```java
@Produces
@ApplicationScoped
HybridCaseRetriever caseRetriever() {
    SparseEmbedder sparseEmbedder = sparseEmbedderInstance.isResolvable()
        ? sparseEmbedderInstance.get() : null;
    CrossEncoderReranker reranker = rerankerInstance.isResolvable()
        ? rerankerInstance.get() : null;
    CurrentPrincipal principal = currentPrincipalInstance.isResolvable()
        ? currentPrincipalInstance.get() : null;
    TenantGuard tenantGuard = TenantGuard.of(principal);
    return new HybridCaseRetriever(
        client,
        embeddingModel,
        sparseEmbedder,
        config.tenancyStrategy(),
        config.denseVectorName(),
        config.sparseVectorName(),
        config.retrieval().denseTopK(),
        config.retrieval().sparseTopK(),
        config.retrieval().rrfK(),
        config.retrieval().rerankEnabled(),
        config.retrieval().rerankTopN(),
        reranker,
        tenantGuard);
}
```

- [ ] **Step 2: Update ReactiveRagBeanProducer**

Same pattern — change `@Inject CurrentPrincipal currentPrincipal;` to `@Inject Instance<CurrentPrincipal> currentPrincipalInstance;`.

Update `corpusStore()`:
```java
@Produces
@ApplicationScoped
ReactiveQdrantEmbeddingIngestor corpusStore() {
    SparseEmbedder sparseEmbedder = sparseEmbedderInstance.isResolvable()
        ? sparseEmbedderInstance.get() : null;
    CurrentPrincipal principal = currentPrincipalInstance.isResolvable()
        ? currentPrincipalInstance.get() : null;
    TenantGuard tenantGuard = TenantGuard.of(principal);
    return new ReactiveQdrantEmbeddingIngestor(
        client, embeddingModel, sparseEmbedder,
        config.tenancyStrategy(),
        config.denseVectorName(), config.sparseVectorName(),
        denseDimension, tenantGuard);
}
```

Update `caseRetriever()`:
```java
@Produces
@ApplicationScoped
ReactiveHybridCaseRetriever caseRetriever() {
    SparseEmbedder sparseEmbedder = sparseEmbedderInstance.isResolvable()
        ? sparseEmbedderInstance.get() : null;
    CrossEncoderReranker reranker = rerankerInstance.isResolvable()
        ? rerankerInstance.get() : null;
    CurrentPrincipal principal = currentPrincipalInstance.isResolvable()
        ? currentPrincipalInstance.get() : null;
    TenantGuard tenantGuard = TenantGuard.of(principal);
    return new ReactiveHybridCaseRetriever(
        client, embeddingModel, sparseEmbedder,
        config.tenancyStrategy(),
        config.denseVectorName(), config.sparseVectorName(),
        config.retrieval().denseTopK(), config.retrieval().sparseTopK(),
        config.retrieval().rrfK(), config.retrieval().rerankEnabled(),
        config.retrieval().rerankTopN(), reranker, tenantGuard);
}
```

- [ ] **Step 3: Verify rag module compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java
git commit -m "feat(#36): bean producers — Instance<CurrentPrincipal> + TenantGuard construction"
```

---

### Task 7: Update existing test constructor calls + add null-principal tests

**Files:**
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/AssertTenantReactiveTest.java`

- [ ] **Step 1: Update QdrantEmbeddingIngestorTest constructor calls**

In `setUp()` (line 62), change:
```java
// Before
store = new QdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse",
    principal
);

// After
store = new QdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse",
    TenantGuard.of(principal)
);
```

In `ingestDenseOnlyMode()` (line 172), change:
```java
// Before
QdrantEmbeddingIngestor denseOnlyStore = new QdrantEmbeddingIngestor(
    client,
    new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
    null,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse",
    RagTestFixtures.stubPrincipal(TENANT)
);

// After
QdrantEmbeddingIngestor denseOnlyStore = new QdrantEmbeddingIngestor(
    client,
    new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
    null,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse",
    TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT))
);
```

Add new null-principal test:
```java
@Test
void ingestWorksWithoutCurrentPrincipal() throws Exception {
    QdrantEmbeddingIngestor noTenantStore = new QdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        TenantGuard.of(null)
    );

    CorpusRef corpus = uniqueCorpus();
    noTenantStore.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));
    assertThat(noTenantStore.listDocuments(corpus)).containsExactly("doc-1");

    noTenantStore.deleteDocument(corpus, "doc-1");
    assertThat(noTenantStore.listDocuments(corpus)).isEmpty();
}
```

- [ ] **Step 2: Update HybridCaseRetrieverTest constructor calls**

In `setUp()` (lines 66–79), change both constructors:
```java
// Before
store = new QdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    principal
);

retriever = new HybridCaseRetriever(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    64, 64, 60,
    false, 10, null,
    principal
);

// After
TenantGuard guard = TenantGuard.of(principal);

store = new QdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    guard
);

retriever = new HybridCaseRetriever(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    64, 64, 60,
    false, 10, null,
    guard
);
```

In `denseOnlyModeIngestAndRetrieve()` (lines 142–155), same pattern — change `principal` to `TenantGuard.of(principal)` in both constructor calls.

Add new null-principal test:
```java
@Test
void retrieveWorksWithoutCurrentPrincipal() {
    TenantGuard noTenantGuard = TenantGuard.of(null);
    EmbeddingModel model = new RagTestFixtures.StubEmbeddingModel(DENSE_DIM);

    QdrantEmbeddingIngestor noTenantStore = new QdrantEmbeddingIngestor(
        client, model, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        noTenantGuard
    );

    HybridCaseRetriever noTenantRetriever = new HybridCaseRetriever(
        client, model, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        64, 64, 60,
        false, 10, null,
        noTenantGuard
    );

    CorpusRef corpus = uniqueCorpus();
    noTenantStore.ingest(corpus, List.of(
        new ChunkInput("searchable content", "doc-1", Map.of())
    ));

    List<RetrievedChunk> results = noTenantRetriever.retrieve(
        "searchable", corpus, 10, null);
    assertThat(results).isNotEmpty();
}
```

- [ ] **Step 3: Update ReactiveQdrantEmbeddingIngestorTest constructor call**

In `setUp()` (line 58), change:
```java
// Before
store = new ReactiveQdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse", DENSE_DIM,
    principal
);

// After
store = new ReactiveQdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse", DENSE_DIM,
    TenantGuard.of(principal)
);
```

Add new null-principal test:
```java
@Test
void ingestWorksWithoutCurrentPrincipal() throws Exception {
    ReactiveQdrantEmbeddingIngestor noTenantStore = new ReactiveQdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse", DENSE_DIM,
        TenantGuard.of(null)
    );

    CorpusRef corpus = uniqueCorpus();
    noTenantStore.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    )).await().indefinitely();
    List<String> docs = noTenantStore.listDocuments(corpus).await().indefinitely();
    assertThat(docs).containsExactly("doc-1");
}
```

- [ ] **Step 4: Update ReactiveHybridCaseRetrieverTest constructor calls**

In `setUp()` (lines 62–76), change both constructors:
```java
// Before
store = new QdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    principal
);

retriever = new ReactiveHybridCaseRetriever(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    64, 64, 60,
    false, 10, null,
    principal
);

// After
TenantGuard guard = TenantGuard.of(principal);

store = new QdrantEmbeddingIngestor(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    guard
);

retriever = new ReactiveHybridCaseRetriever(
    client, embeddingModel, sparseEmbedder,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
    64, 64, 60,
    false, 10, null,
    guard
);
```

Add new null-principal test:
```java
@Test
void retrieveWorksWithoutCurrentPrincipal() {
    TenantGuard noTenantGuard = TenantGuard.of(null);
    EmbeddingModel model = new RagTestFixtures.StubEmbeddingModel(DENSE_DIM);

    QdrantEmbeddingIngestor noTenantStore = new QdrantEmbeddingIngestor(
        client, model, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        noTenantGuard
    );

    noTenantStore.ingest(uniqueCorpus(), List.of(
        new ChunkInput("searchable content", "doc-1", Map.of())
    ));

    ReactiveHybridCaseRetriever noTenantRetriever = new ReactiveHybridCaseRetriever(
        client, model, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        64, 64, 60,
        false, 10, null,
        noTenantGuard
    );

    CorpusRef corpus = uniqueCorpus();
    noTenantStore.ingest(corpus, List.of(
        new ChunkInput("searchable content", "doc-1", Map.of())
    ));

    List<RetrievedChunk> results = noTenantRetriever.retrieve(
        "searchable", corpus, 10, null).await().indefinitely();
    assertThat(results).isNotEmpty();
}
```

- [ ] **Step 5: Update AssertTenantReactiveTest constructor calls**

In `createIngestor()` (line 78), change:
```java
// Before
return new ReactiveQdrantEmbeddingIngestor(
    null, null, null,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse", 4,
    RagTestFixtures.stubPrincipal(TENANT));

// After
return new ReactiveQdrantEmbeddingIngestor(
    null, null, null,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse", 4,
    TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)));
```

In `createRetriever()` (line 86), change:
```java
// Before
return new ReactiveHybridCaseRetriever(
    null, null, null,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse",
    64, 64, 60,
    false, 10, null,
    RagTestFixtures.stubPrincipal(TENANT));

// After
return new ReactiveHybridCaseRetriever(
    null, null, null,
    TenancyStrategy.SEPARATE_COLLECTIONS,
    "dense", "sparse",
    64, 64, 60,
    false, 10, null,
    TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)));
```

- [ ] **Step 6: Run all rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: PASS — all existing tests pass with updated constructors, plus new null-principal tests pass

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(#36): update all test constructor calls + add null-principal tests"
```

---

### Task 8: Full build verification

**Files:** None — verification only.

- [ ] **Step 1: Full build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: PASS — all modules compile and all tests pass

- [ ] **Step 2: Build examples with smoke profile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples-smoke`
Expected: PASS

- [ ] **Step 3: Commit if any fixups needed**

If any fixes were applied during verification:
```bash
git add -A
git commit -m "fix(#36): build verification fixups"
```

---

### Task 9: ARC42STORIES updates

**Files:**
- Modify: `ARC42STORIES.MD`

Apply all updates from the spec's ARC42STORIES update table. The exact current→updated text for each section is in the spec.

- [ ] **Step 1: Update §1 stakeholders table — Hortora row**

```
// Before
| Hortora | SPLADE sparse embeddings + CrossEncoderReranker — takes inference-* only |

// After
| Hortora | SPLADE, CrossEncoderReranker (inference-*) + EmbeddingIngestor, CaseRetriever, CorpusIngestionService (rag-*) |
```

- [ ] **Step 2: Update §1 Top Quality Goals — tenancy row**

```
// Before
| 4 | **Tenancy isolation** | Every `CaseRetriever.retrieve()` is tenancy-scoped; cross-tenant retrieval is blocked at the SPI boundary |

// After
| 4 | **Tenancy isolation** | Every `CaseRetriever.retrieve()` is tenancy-scoped; cross-tenant retrieval is blocked when `CurrentPrincipal` is provided. Single-tenant consumers opt out via `TenantGuard` |
```

- [ ] **Step 3: Update §2 constraints — full paragraph replacement**

```
// Before
**Hortora shares inference-* only** — `rag-*` modules are casehub-specific. Hortora wires their own LangChain4j RAG stack independently. No code is shared between the two RAG wiring layers.

// After
**Hortora shares inference-* and rag-*** — `rag-*` modules support optional tenancy for non-casehub consumers (#36). Hortora depends on `rag-api` (SPIs), `rag` (Qdrant implementation), and `rag-testing` (in-memory stubs). Tenancy enforcement is active when a `CurrentPrincipal` bean is provided (all casehub deployments); single-tenant consumers opt out by not providing the bean. `casehub-platform-api` remains a transitive dependency of `rag/` — version coordination required.
```

- [ ] **Step 4: Update §3 context diagram**

```mermaid
// Before
Person(hortora, "Hortora", "Takes inference-* modules; wires own RAG stack")
...
Rel(hortora, inference, "Takes inference-* as dependency")

// After
Person(hortora, "Hortora", "Takes inference-* and rag-* modules")
...
Rel(hortora, inference, "Takes inference-* as dependency")
Rel(hortora, rag, "Takes rag-* as dependency")
```

- [ ] **Step 5: Update §4 Solution Strategy — tenancy text**

```
// Before
**Tenancy isolation at the SPI boundary** — `CaseRetriever.retrieve()` and `EmbeddingIngestor.ingest()` require a `CorpusRef` carrying the tenant ID. No cross-tenant retrieval is possible through the SPI. Qdrant payload filtering enforces isolation at the storage layer.

// After
**Tenancy isolation at the SPI boundary** — `CaseRetriever.retrieve()` and `EmbeddingIngestor.ingest()` require a `CorpusRef` carrying the tenant ID. No cross-tenant retrieval is possible through the SPI when `CurrentPrincipal` is provided. Single-tenant consumers that do not provide a `CurrentPrincipal` opt out of tenant enforcement by design. Qdrant payload filtering enforces isolation at the storage layer.
```

- [ ] **Step 6: Update §5 layer table — L6 and L7**

```
// Before
| L6 RAG SPI | `rag-api`, `rag-testing` | Pure Java, zero deps | casehub only |
| L7 RAG Runtime | `rag` | Quarkus + LangChain4j | casehub only |

// After
| L6 RAG SPI | `rag-api`, `rag-testing` | Pure Java, zero deps | ✅ yes |
| L7 RAG Runtime | `rag` | Quarkus + LangChain4j | ✅ yes |
```

- [ ] **Step 7: Update §8 Crosscutting — tenancy isolation paragraph**

```
// Before
`CorpusRef` carries `tenantId`. `CaseRetriever.retrieve()` passes tenant ID as a Qdrant payload filter on every query. No cross-tenant retrieval is possible through the SPI. Cross-tenant access requires a separate `@CrossTenant`-qualified bean (not yet defined — file issue when needed).

// After
`CorpusRef` carries `tenantId`. `CaseRetriever.retrieve()` passes tenant ID as a Qdrant payload filter on every query. No cross-tenant retrieval is possible through the SPI when `CurrentPrincipal` is provided (all casehub deployments). Single-tenant consumers that do not provide a `CurrentPrincipal` opt out of tenant enforcement by design — `TenantGuard` no-ops. Cross-tenant access requires a separate `@CrossTenant`-qualified bean (not yet defined — file issue when needed).
```

- [ ] **Step 8: Update §10 AD-001**

```
// Before
Hortora ignores `rag-*` by depending only on `inference-*` artifacts.

// After
Hortora takes both `inference-*` and `rag-*` artifacts (#35). Tenancy enforcement is optional for single-tenant consumers (#36).
```

- [ ] **Step 9: Update §11 Quality Requirements — tenancy row**

```
// Before
| Tenancy isolation | Tenant A cannot retrieve Tenant B's corpus | Configurable TenancyStrategy: separate Qdrant collections per tenant (default, hard isolation) or shared collection with payload filter on tenantId; enforced by CorpusRef type |

// After
| Tenancy isolation | Tenant A cannot retrieve Tenant B's corpus when `CurrentPrincipal` is provided | Configurable TenancyStrategy + `TenantGuard`; enforced when `CurrentPrincipal` bean is present |
```

- [ ] **Step 10: Update §12 risk table — Hortora row**

```
// Before
| Hortora's usage pattern conflicts with SPI design | Medium | Medium | C3 complete — SPI design validated through implementation; Hortora integration pending their adoption |

// After
| Hortora's usage pattern conflicts with SPI design | Low | Medium | rag-* consumption enabled (#35); tenancy optionality shipped (#36); Hortora adoption pending |
```

- [ ] **Step 11: Commit**

```bash
git add ARC42STORIES.MD
git commit -m "docs(#36): update ARC42STORIES — Hortora boundary shift, conditional tenancy"
```

---

### Task 10: Issue documentation + cross-repo issue

**Files:** None — GitHub issue comments and issue creation.

- [ ] **Step 1: Update #36 with integration guide**

Comment on casehubio/neural-text#36 with gaps 2–5 documentation:

**Gap 2 — Ingestion orchestration:** Recommend Path A (use `CorpusIngestionService` via `CorpusIngestionBinding` CDI bean). Hortora is Quarkus 3.32.2 — all framework deps available. Drops the most duplicated code. Path B (direct `EmbeddingIngestor`) available for non-Quarkus consumers.

**Gap 3 — engine#521:** Not relevant to Hortora — targets existing casehub consumers updating from 3-param to 4-param `retrieve()`.

**Gap 4 — Collection schema upgrade:** Qdrant collection schemas are immutable. Dense-only → hybrid requires drop collection + full re-index.

**Gap 5 — platform-api transitive:** `casehub-rag` transitively pulls `casehub-platform-api` (0.2-SNAPSHOT). Zero-dep pure-Java, safe on classpath. Risk: version coordination — `CurrentPrincipal` interface changes break Hortora's build. Mitigation: stable releases for `casehub-platform-api`.

- [ ] **Step 2: Comment on engine#521 clarifying scope**

```bash
gh issue comment 521 --repo casehubio/engine --body "This issue targets existing casehub consumers updating CaseRetriever call sites from the 3-param to 4-param signature (PayloadFilter parameter added in neural-text#35). Hortora/engine adopts the new 4-param API directly — this issue is not relevant to Hortora integration."
```

- [ ] **Step 3: File issue on casehubio/parent for PLATFORM.MD deep-dive update**

```bash
gh issue create --repo casehubio/parent --title "docs: update neural-text deep-dive — Hortora now takes rag-* modules" --body "$(cat <<'EOF'
## Context

neural-text#35 made rag-* modules consumable by Hortora. neural-text#36 added optional tenancy (TenantGuard). The deep-dive at docs/repos/casehub-neural-text.md still says:

> The rag-* modules are casehub-specific — Hortora does not take them.

## Change needed

Update the "Shared with Hortora" section to reflect that Hortora now takes rag-api, rag, and rag-testing in addition to inference-*. Note that tenancy enforcement is optional — active when CurrentPrincipal is provided, no-ops when absent.

## Refs

- neural-text#35 (boundary change)
- neural-text#36 (TenantGuard)
EOF
)"
```

- [ ] **Step 4: Commit** (no files to commit — this task is GitHub-only)

---

Now the self-review.

**1. Spec coverage:**
- Change 1 (TenantGuard) → Tasks 1–7 ✅
- Constructor visibility → Tasks 2–5 (constructors changed to package-private) ✅
- Bean producer changes → Task 6 ✅
- Test plan (mechanical updates + null-principal) → Task 7 ✅
- Full build verification → Task 8 ✅
- ARC42STORIES updates (§1, §2, §3, §4, §5, §8, §10, §11, §12) → Task 9 ✅
- Gaps 2–5 documentation → Task 10 ✅
- Cross-repo parent issue → Task 10 Step 3 ✅

**2. Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks are complete. All commands have expected output.

**3. Type consistency:** `TenantGuard` used consistently everywhere — field type, constructor parameter, `TenantGuard.of(principal)` in tests, `TenantGuard.of(null)` in null-principal tests. `tenantGuard.assertTenant(corpus.tenantId())` at all call sites.
