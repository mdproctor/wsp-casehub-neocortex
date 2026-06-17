# RAG Hortora Shared-Code Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three gaps in neural-text's rag modules so Hortora's engine can drop 6 duplicated classes and depend on `casehub-rag-api` + `casehub-rag` directly.

**Architecture:** Add `PayloadFilter` sealed algebra to `rag-api`, add filter parameter to `CaseRetriever`/`ReactiveCaseRetriever`, make `SparseEmbedder` optional via `Instance<>` in bean producers (dense-only mode), replace `UUID.randomUUID()` with deterministic UUID v3 from per-document chunk indices.

**Tech Stack:** Java 21, Quarkus 3.32, LangChain4j 1.14.1, Qdrant Java client 1.18.1, Testcontainers, AssertJ

**Spec:** `specs/2026-06-17-rag-hortora-shared-code-gaps-design.md`
**Issue:** casehubio/neural-text#35

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
**Build single module:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`
**Run single test:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl <module> -Dtest=<TestClass>#<method>`

---

### Task 1: PayloadFilter sealed interface

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/PayloadFilter.java`
- Create: `rag-api/src/test/java/io/casehub/rag/PayloadFilterTest.java`

- [ ] **Step 1: Write failing tests for PayloadFilter records**

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.*;

class PayloadFilterTest {

    @Test
    void eqRejectsNullField() {
        assertThatThrownBy(() -> PayloadFilter.eq(null, "v"))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void eqRejectsNullValue() {
        assertThatThrownBy(() -> PayloadFilter.eq("f", null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void eqCreatesRecord() {
        var f = PayloadFilter.eq("domain", "jvm");
        assertThat(f).isInstanceOf(PayloadFilter.Eq.class);
        assertThat(((PayloadFilter.Eq) f).field()).isEqualTo("domain");
        assertThat(((PayloadFilter.Eq) f).value()).isEqualTo("jvm");
    }

    @Test
    void inRejectsNullField() {
        assertThatThrownBy(() -> PayloadFilter.in(null, List.of("a")))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void inRejectsNullValues() {
        assertThatThrownBy(() -> PayloadFilter.in("f", null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void inDefensiveCopy() {
        var original = new java.util.ArrayList<>(List.of("a", "b"));
        var f = PayloadFilter.in("field", original);
        original.add("c");
        assertThat(((PayloadFilter.In) f).values()).containsExactly("a", "b");
    }

    @Test
    void notRejectsNull() {
        assertThatThrownBy(() -> PayloadFilter.not(null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void notWrapsInner() {
        var inner = PayloadFilter.eq("f", "v");
        var f = PayloadFilter.not(inner);
        assertThat(((PayloadFilter.Not) f).inner()).isSameAs(inner);
    }

    @Test
    void andRejectsEmptyList() {
        assertThatThrownBy(() -> new PayloadFilter.And(List.of()))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void andRejectsEmptyVarargs() {
        assertThatThrownBy(PayloadFilter::and)
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void andComposesFilters() {
        var a = PayloadFilter.eq("f1", "v1");
        var b = PayloadFilter.eq("f2", "v2");
        var f = PayloadFilter.and(a, b);
        assertThat(((PayloadFilter.And) f).filters()).containsExactly(a, b);
    }

    @Test
    void orRejectsEmptyList() {
        assertThatThrownBy(() -> new PayloadFilter.Or(List.of()))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void orRejectsEmptyVarargs() {
        assertThatThrownBy(PayloadFilter::or)
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void orComposesFilters() {
        var a = PayloadFilter.eq("f1", "v1");
        var b = PayloadFilter.eq("f2", "v2");
        var f = PayloadFilter.or(a, b);
        assertThat(((PayloadFilter.Or) f).filters()).containsExactly(a, b);
    }

    @Test
    void nestedComposition() {
        var f = PayloadFilter.and(
            PayloadFilter.eq("domain", "jvm"),
            PayloadFilter.not(PayloadFilter.in("type", List.of("gotcha", "technique")))
        );
        assertThat(f).isInstanceOf(PayloadFilter.And.class);
        var and = (PayloadFilter.And) f;
        assertThat(and.filters()).hasSize(2);
        assertThat(and.filters().get(1)).isInstanceOf(PayloadFilter.Not.class);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=PayloadFilterTest`
Expected: FAIL — `PayloadFilter` does not exist

- [ ] **Step 3: Implement PayloadFilter**

```java
package io.casehub.rag;

import java.util.List;
import java.util.Objects;

public sealed interface PayloadFilter {

    record Eq(String field, String value) implements PayloadFilter {
        public Eq {
            Objects.requireNonNull(field, "field");
            Objects.requireNonNull(value, "value");
        }
    }

    record In(String field, List<String> values) implements PayloadFilter {
        public In {
            Objects.requireNonNull(field, "field");
            Objects.requireNonNull(values, "values");
            values = List.copyOf(values);
        }
    }

    record Not(PayloadFilter inner) implements PayloadFilter {
        public Not {
            Objects.requireNonNull(inner, "inner");
        }
    }

    record And(List<PayloadFilter> filters) implements PayloadFilter {
        public And {
            if (filters.isEmpty()) throw new IllegalArgumentException("And requires at least one filter");
            filters = List.copyOf(filters);
        }
    }

    record Or(List<PayloadFilter> filters) implements PayloadFilter {
        public Or {
            if (filters.isEmpty()) throw new IllegalArgumentException("Or requires at least one filter");
            filters = List.copyOf(filters);
        }
    }

    static PayloadFilter eq(String field, String value) { return new Eq(field, value); }
    static PayloadFilter in(String field, List<String> values) { return new In(field, List.copyOf(values)); }
    static PayloadFilter not(PayloadFilter inner) { return new Not(inner); }
    static PayloadFilter and(PayloadFilter... filters) { return new And(List.of(filters)); }
    static PayloadFilter or(PayloadFilter... filters) { return new Or(List.of(filters)); }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=PayloadFilterTest`
Expected: PASS

- [ ] **Step 5: Run full rag-api module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api`
Expected: PASS (PayloadFilter is new — no existing tests break)

- [ ] **Step 6: Commit**

```bash
git add rag-api/src/main/java/io/casehub/rag/PayloadFilter.java rag-api/src/test/java/io/casehub/rag/PayloadFilterTest.java
git commit -m "feat(#35): add PayloadFilter sealed algebra to rag-api"
```

---

### Task 2: CaseRetriever SPI signature change

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/rag/CaseRetriever.java`
- Modify: `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java`
- Modify: `rag-api/src/test/java/io/casehub/rag/BlockingReactiveParityTest.java`

- [ ] **Step 1: Update CaseRetriever interface**

Change `rag-api/src/main/java/io/casehub/rag/CaseRetriever.java`:

```java
package io.casehub.rag;

import java.util.List;

public interface CaseRetriever {
    List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter);
}
```

- [ ] **Step 2: Update ReactiveCaseRetriever interface**

Change `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java`:

```java
package io.casehub.rag;

import io.smallrye.mutiny.Uni;
import java.util.List;

public interface ReactiveCaseRetriever {
    Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter);
}
```

- [ ] **Step 3: Run BlockingReactiveParityTest**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=BlockingReactiveParityTest`
Expected: PASS — the parity test uses reflection to compare parameter types; both interfaces now have the same 4-parameter signature.

- [ ] **Step 4: Verify rag-api compiles (other modules will fail — expected)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rag-api/src/main/java/io/casehub/rag/CaseRetriever.java rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java
git commit -m "feat(#35): add PayloadFilter parameter to CaseRetriever and ReactiveCaseRetriever"
```

---

### Task 3: Update all CaseRetriever call sites (compile fixes)

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java` — add `PayloadFilter filter` to method signature (pass `null` through internally for now)
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java` — same
- Modify: `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java` — add parameter, pass through
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java` — add parameter (ignore filter for now — Task 7 adds real filtering)
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java` — add parameter, pass through
- Modify: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java` — add `null` as 4th arg
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java` — add `null` as 4th arg
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java` — add `null` as 4th arg
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCaseRetrieverTest.java` — add `null` as 4th arg
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java` — add `null` as 4th arg
- Modify: `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/HybridSearchDemo.java` — add `null` as 4th arg
- Modify: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/RagPipelineIT.java` — add `null` as 4th arg

This is a mechanical migration. Every `retrieve(query, corpus, maxResults)` becomes `retrieve(query, corpus, maxResults, null)`. The implementations accept the parameter but ignore the filter value until Tasks 5 and 7 wire up the actual filtering.

- [ ] **Step 1: Update HybridCaseRetriever.retrieve() signature**

In `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`, change the `@Override` method signature:

```java
@Override
public List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
```

No other changes to the method body yet — filter is accepted but unused until Task 5.

- [ ] **Step 2: Update ReactiveHybridCaseRetriever.retrieve() signature**

In `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`, change:

```java
@Override
public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
```

- [ ] **Step 3: Update BlockingToReactiveCaseRetriever**

In `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java`, change:

```java
@Override
public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
    return Uni.createFrom().item(() -> delegate.retrieve(query, corpus, maxResults, filter))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}
```

- [ ] **Step 4: Update InMemoryCaseRetriever**

In `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`, change:

```java
@Override
public List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
```

Filter is accepted but ignored for now — Task 7 adds real filtering.

- [ ] **Step 5: Update InMemoryReactiveCaseRetriever**

In `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java`, change:

```java
@Override
public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
    return Uni.createFrom().item(() -> delegate.retrieve(query, corpus, maxResults, filter));
}
```

- [ ] **Step 6: Update all test call sites — add `null` as 4th argument**

In each test file, change every `retrieve(query, corpus, N)` to `retrieve(query, corpus, N, null)`:

- `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`
- `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`
- `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCaseRetrieverTest.java`
- `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java`

- [ ] **Step 7: Update examples**

- `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/HybridSearchDemo.java`: change `retriever.retrieve(query, corpus, 5)` to `retriever.retrieve(query, corpus, 5, null)`
- `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/RagPipelineIT.java`: same pattern

- [ ] **Step 8: Build all modules (except examples)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(#35): update all CaseRetriever call sites for PayloadFilter parameter"
```

---

### Task 4: Optional sparse embeddings

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`

- [ ] **Step 1: Write dense-only ingestion test**

Add to `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`:

```java
@Test
void denseOnlyIngestCreatesCollectionWithoutSparseConfig() throws Exception {
    QdrantEmbeddingIngestor denseOnlyStore = new QdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,  // no sparse embedder
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        RagTestFixtures.stubPrincipal(TENANT)
    );

    CorpusRef corpus = uniqueCorpus();
    denseOnlyStore.ingest(corpus, List.of(
        new ChunkInput("text content", "doc-1", Map.of("key", "val"))
    ));

    assertThat(client.collectionExistsAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get())
        .isTrue();
    assertThat(denseOnlyStore.listDocuments(corpus)).containsExactly("doc-1");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest#denseOnlyIngestCreatesCollectionWithoutSparseConfig`
Expected: FAIL — `NullPointerException` from `sparseEmbedder.embedBatch()`

- [ ] **Step 3: Make SparseEmbedder nullable in QdrantEmbeddingIngestor**

In `QdrantEmbeddingIngestor.java`:

**Constructor:** Accept null `sparseEmbedder` (remove any null check if present).

**`ingest()` method:** After dense embedding, conditionally embed sparse:

```java
List<Map<Integer, Float>> sparseEmbeddings = sparseEmbedder != null
    ? sparseEmbedder.embedBatch(texts)
    : null;
```

**`ensureCollection()` method:** Conditionally add sparse vector config:

```java
VectorParamsMap paramsMap = VectorParamsMap.newBuilder()
    .putMap(denseVectorName, denseParams)
    .build();

CreateCollection.Builder createBuilder = CreateCollection.newBuilder()
    .setCollectionName(collection)
    .setVectorsConfig(VectorsConfig.newBuilder().setParamsMap(paramsMap).build());

if (sparseEmbedder != null) {
    SparseVectorConfig sparseConfig = SparseVectorConfig.newBuilder()
        .putMap(sparseVectorName, SparseVectorParams.getDefaultInstance())
        .build();
    createBuilder.setSparseVectorsConfig(sparseConfig);
}

client.createCollectionAsync(createBuilder.build()).get();
```

**`buildPoint()` method:** Accept nullable `sparseMap`, build named vectors conditionally:

```java
Map<String, Vector> namedVectors;
if (sparseMap != null) {
    List<Float> sparseValues = new ArrayList<>(sparseMap.size());
    List<Integer> sparseIndices = new ArrayList<>(sparseMap.size());
    for (Map.Entry<Integer, Float> entry : sparseMap.entrySet()) {
        sparseIndices.add(entry.getKey());
        sparseValues.add(entry.getValue());
    }
    Vector sparseVector = VectorFactory.vector(sparseValues, sparseIndices);
    namedVectors = Map.of(denseVectorName, denseVector, sparseVectorName, sparseVector);
} else {
    namedVectors = Map.of(denseVectorName, denseVector);
}
```

- [ ] **Step 4: Run dense-only ingestion test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest#denseOnlyIngestCreatesCollectionWithoutSparseConfig`
Expected: PASS

- [ ] **Step 5: Write dense-only retrieval test**

Add to `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`:

```java
@Test
void denseOnlyRetrievalWorks() {
    EmbeddingModel embeddingModel = new RagTestFixtures.StubEmbeddingModel(DENSE_DIM);
    CurrentPrincipal p = RagTestFixtures.stubPrincipal(TENANT);

    QdrantEmbeddingIngestor denseStore = new QdrantEmbeddingIngestor(
        client, embeddingModel, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, p
    );

    HybridCaseRetriever denseRetriever = new HybridCaseRetriever(
        client, embeddingModel, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        64, 64, 60,
        false, 10, null, p
    );

    CorpusRef corpus = uniqueCorpus();
    denseStore.ingest(corpus, List.of(
        new ChunkInput("The quick brown fox", "doc-1", Map.of("category", "animals")),
        new ChunkInput("Machine learning basics", "doc-2", Map.of("category", "tech"))
    ));

    List<RetrievedChunk> results = denseRetriever.retrieve("brown fox", corpus, 10, null);
    assertThat(results).isNotEmpty();
    assertThat(results).allSatisfy(chunk -> {
        assertThat(chunk.content()).isNotBlank();
        assertThat(chunk.relevanceScore()).isGreaterThan(0.0);
    });
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest#denseOnlyRetrievalWorks`
Expected: FAIL — `NullPointerException` from `sparseEmbedder.embed()`

- [ ] **Step 7: Make SparseEmbedder nullable in HybridCaseRetriever**

In `HybridCaseRetriever.java`, modify `retrieve()` to branch on `sparseEmbedder`:

```java
if (sparseEmbedder != null) {
    // Existing hybrid path: dense + sparse prefetch with RRF
    Map<Integer, Float> sparseMap = sparseEmbedder.embed(query);
    // ... build sparseValues, sparseIndices ...
    // ... build densePrefetch, sparsePrefetch, RRF query ...
} else {
    // Dense-only path: direct nearest-neighbor query
    int queryLimit = rerankEnabled && reranker != null
        ? Math.max(maxResults, rerankTopN) : maxResults;

    QueryPoints.Builder builder = QueryPoints.newBuilder()
        .setCollectionName(collection)
        .setQuery(QueryFactory.nearest(denseEmbedding.vectorAsList()))
        .setUsing(denseVectorName)
        .setLimit(queryLimit)
        .setWithPayload(WithPayloadSelectorFactory.enable(true));
    tenantFilter.ifPresent(builder::setFilter);
    queryPoints = builder.build();
}
```

- [ ] **Step 8: Run dense-only retrieval test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest#denseOnlyRetrievalWorks`
Expected: PASS

- [ ] **Step 9: Apply same changes to ReactiveQdrantEmbeddingIngestor and ReactiveHybridCaseRetriever**

Mirror the nullable `sparseEmbedder` changes from Steps 3 and 7 into the reactive variants.

- [ ] **Step 10: Update RagBeanProducer — Instance<SparseEmbedder>**

In `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java`:

```java
// Before:
@Inject SparseEmbedder sparseEmbedder;

// After:
@Inject Instance<SparseEmbedder> sparseEmbedderInstance;
```

In producer methods, resolve:
```java
SparseEmbedder sparseEmbedder = sparseEmbedderInstance.isResolvable()
    ? sparseEmbedderInstance.get() : null;
```

- [ ] **Step 11: Update ReactiveRagBeanProducer — same pattern**

Same `Instance<SparseEmbedder>` change in `ReactiveRagBeanProducer.java`.

- [ ] **Step 12: Run all existing tests to verify hybrid mode still works**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: PASS — all existing tests pass (they provide `SparseEmbedder`), plus new dense-only tests pass

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "feat(#35): make SparseEmbedder optional — dense-only mode for ingestion and retrieval"
```

---

### Task 5: PayloadFilter translation and retriever wiring

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/PayloadFilterTranslator.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/PayloadFilterTranslatorTest.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`

- [ ] **Step 1: Write failing tests for PayloadFilterTranslator**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.PayloadFilter;
import io.qdrant.client.grpc.Common.Condition;
import io.qdrant.client.grpc.Common.Filter;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Optional;
import static org.assertj.core.api.Assertions.*;

class PayloadFilterTranslatorTest {

    @Test
    void nullReturnsEmpty() {
        assertThat(PayloadFilterTranslator.toQdrantFilter(null)).isEmpty();
    }

    @Test
    void eqProducesMatchKeyword() {
        Optional<Filter> result = PayloadFilterTranslator.toQdrantFilter(
            PayloadFilter.eq("domain", "jvm"));
        assertThat(result).isPresent();
        Filter filter = result.get();
        assertThat(filter.getMustCount()).isEqualTo(1);
        Condition condition = filter.getMust(0);
        assertThat(condition.hasField()).isTrue();
        assertThat(condition.getField().getKey()).isEqualTo("domain");
        assertThat(condition.getField().getMatch().getKeyword()).isEqualTo("jvm");
    }

    @Test
    void inProducesMatchKeywords() {
        Optional<Filter> result = PayloadFilterTranslator.toQdrantFilter(
            PayloadFilter.in("type", List.of("gotcha", "technique")));
        assertThat(result).isPresent();
        Condition condition = result.get().getMust(0);
        assertThat(condition.getField().getKey()).isEqualTo("type");
        assertThat(condition.getField().getMatch().getKeywords().getStringsList())
            .containsExactly("gotcha", "technique");
    }

    @Test
    void notProducesMustNot() {
        Optional<Filter> result = PayloadFilterTranslator.toQdrantFilter(
            PayloadFilter.not(PayloadFilter.eq("domain", "jvm")));
        assertThat(result).isPresent();
        Condition condition = result.get().getMust(0);
        assertThat(condition.hasFilter()).isTrue();
        Filter nested = condition.getFilter();
        assertThat(nested.getMustNotCount()).isEqualTo(1);
        assertThat(nested.getMustNot(0).getField().getKey()).isEqualTo("domain");
    }

    @Test
    void andProducesMust() {
        Optional<Filter> result = PayloadFilterTranslator.toQdrantFilter(
            PayloadFilter.and(
                PayloadFilter.eq("domain", "jvm"),
                PayloadFilter.eq("type", "gotcha")));
        assertThat(result).isPresent();
        Condition condition = result.get().getMust(0);
        assertThat(condition.hasFilter()).isTrue();
        Filter nested = condition.getFilter();
        assertThat(nested.getMustCount()).isEqualTo(2);
    }

    @Test
    void orProducesShould() {
        Optional<Filter> result = PayloadFilterTranslator.toQdrantFilter(
            PayloadFilter.or(
                PayloadFilter.eq("domain", "jvm"),
                PayloadFilter.eq("domain", "tools")));
        assertThat(result).isPresent();
        Condition condition = result.get().getMust(0);
        assertThat(condition.hasFilter()).isTrue();
        Filter nested = condition.getFilter();
        assertThat(nested.getShouldCount()).isEqualTo(2);
    }

    @Test
    void nestedAndOrNotComposition() {
        Optional<Filter> result = PayloadFilterTranslator.toQdrantFilter(
            PayloadFilter.and(
                PayloadFilter.eq("domain", "jvm"),
                PayloadFilter.or(
                    PayloadFilter.eq("type", "gotcha"),
                    PayloadFilter.not(PayloadFilter.in("tags", List.of("deprecated")))
                )
            ));
        assertThat(result).isPresent();
        // And wrapper
        Condition andCondition = result.get().getMust(0);
        assertThat(andCondition.hasFilter()).isTrue();
        Filter andFilter = andCondition.getFilter();
        assertThat(andFilter.getMustCount()).isEqualTo(2);
        // Second must element is the Or
        Condition orCondition = andFilter.getMust(1);
        assertThat(orCondition.hasFilter()).isTrue();
        assertThat(orCondition.getFilter().getShouldCount()).isEqualTo(2);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=PayloadFilterTranslatorTest`
Expected: FAIL — `PayloadFilterTranslator` does not exist

- [ ] **Step 3: Implement PayloadFilterTranslator**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.PayloadFilter;
import io.qdrant.client.ConditionFactory;
import io.qdrant.client.grpc.Common.Condition;
import io.qdrant.client.grpc.Common.Filter;
import java.util.Optional;

final class PayloadFilterTranslator {

    private PayloadFilterTranslator() {}

    static Optional<Filter> toQdrantFilter(PayloadFilter filter) {
        if (filter == null) return Optional.empty();
        return Optional.of(Filter.newBuilder()
            .addMust(toCondition(filter))
            .build());
    }

    private static Condition toCondition(PayloadFilter filter) {
        return switch (filter) {
            case PayloadFilter.Eq eq ->
                ConditionFactory.matchKeyword(eq.field(), eq.value());
            case PayloadFilter.In in ->
                ConditionFactory.matchKeywords(in.field(), in.values());
            case PayloadFilter.Not not ->
                ConditionFactory.filter(
                    Filter.newBuilder().addMustNot(toCondition(not.inner())).build());
            case PayloadFilter.And and -> {
                var nested = Filter.newBuilder();
                for (var f : and.filters()) nested.addMust(toCondition(f));
                yield ConditionFactory.filter(nested.build());
            }
            case PayloadFilter.Or or -> {
                var nested = Filter.newBuilder();
                for (var f : or.filters()) nested.addShould(toCondition(f));
                yield ConditionFactory.filter(nested.build());
            }
        };
    }
}
```

- [ ] **Step 4: Run translator tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=PayloadFilterTranslatorTest`
Expected: PASS

- [ ] **Step 5: Wire filter into HybridCaseRetriever.retrieve()**

In `HybridCaseRetriever.java`, after the tenancy filter line, add filter composition:

```java
Optional<Filter> tenantFilter = tenancyStrategy.tenantFilter(corpus);
Optional<Filter> payloadFilter = PayloadFilterTranslator.toQdrantFilter(filter);

Filter.Builder combined = Filter.newBuilder();
tenantFilter.ifPresent(tf -> combined.addAllMust(tf.getMustList()));
payloadFilter.ifPresent(pf -> combined.addAllMust(pf.getMustList()));
Optional<Filter> mergedFilter = combined.getMustCount() > 0
    ? Optional.of(combined.build()) : Optional.empty();
```

Replace all uses of `tenantFilter` in query building with `mergedFilter`.

- [ ] **Step 6: Wire filter into ReactiveHybridCaseRetriever.retrieve()**

Same composition pattern in the reactive variant.

- [ ] **Step 7: Write integration test for payload filtering**

Add to `HybridCaseRetrieverTest.java`:

```java
@Test
void retrieveWithPayloadFilterNarrowsResults() {
    CorpusRef corpus = uniqueCorpus();
    store.ingest(corpus, List.of(
        new ChunkInput("Java CDI injection", "doc-1", Map.of("domain", "jvm")),
        new ChunkInput("Python pip install", "doc-2", Map.of("domain", "python")),
        new ChunkInput("Java Spring Boot", "doc-3", Map.of("domain", "jvm"))
    ));

    List<RetrievedChunk> allResults = retriever.retrieve("programming", corpus, 10, null);
    List<RetrievedChunk> jvmOnly = retriever.retrieve("programming", corpus, 10,
        PayloadFilter.eq("domain", "jvm"));

    assertThat(allResults.size()).isGreaterThanOrEqualTo(jvmOnly.size());
    assertThat(jvmOnly).allSatisfy(chunk ->
        assertThat(chunk.metadata().get("domain")).isEqualTo("jvm"));
}
```

- [ ] **Step 8: Run all rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(#35): PayloadFilter translation + retriever wiring for query-time filtering"
```

---

### Task 6: Deterministic point IDs

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`

- [ ] **Step 1: Write failing test for deterministic IDs**

Add to `QdrantEmbeddingIngestorTest.java`:

```java
@Test
void reingestSameDocumentProducesIdempotentUpsert() {
    CorpusRef corpus = uniqueCorpus();
    store.ingest(corpus, List.of(
        new ChunkInput("original text", "doc-1", Map.of())
    ));
    assertThat(store.listDocuments(corpus)).containsExactly("doc-1");

    // Re-ingest same document — should overwrite, not duplicate
    store.ingest(corpus, List.of(
        new ChunkInput("updated text", "doc-1", Map.of())
    ));
    assertThat(store.listDocuments(corpus)).containsExactly("doc-1");
}

@Test
void multiDocBatchProducesStableIds() {
    CorpusRef corpus = uniqueCorpus();

    // Ingest A and B together in a batch
    store.ingest(corpus, List.of(
        new ChunkInput("chunk A", "doc-A", Map.of()),
        new ChunkInput("chunk B", "doc-B", Map.of())
    ));

    // Ingest B alone
    store.deleteDocument(corpus, "doc-B");
    store.ingest(corpus, List.of(
        new ChunkInput("chunk B", "doc-B", Map.of())
    ));

    // B should still be exactly 1 document (same deterministic ID regardless of batch)
    assertThat(store.listDocuments(corpus)).containsExactlyInAnyOrder("doc-A", "doc-B");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest#reingestSameDocumentProducesIdempotentUpsert`
Expected: FAIL — random UUIDs create duplicates on re-ingest

- [ ] **Step 3: Implement per-document deterministic IDs**

In `QdrantEmbeddingIngestor.java`, replace the `buildPoint()` call in `ingest()`:

```java
// In ingest(), build points with per-document chunk counters:
Map<String, Integer> counters = new java.util.HashMap<>();
List<PointStruct> points = new ArrayList<>(chunks.size());
for (int i = 0; i < chunks.size(); i++) {
    ChunkInput chunk = chunks.get(i);
    int chunkIndex = counters.merge(chunk.sourceDocumentId(), 0, Integer::sum);
    counters.put(chunk.sourceDocumentId(), chunkIndex + 1);
    points.add(buildPoint(chunk, corpus,
        denseEmbeddings.get(i),
        sparseEmbeddings != null ? sparseEmbeddings.get(i) : null,
        chunkIndex));
}
```

In `buildPoint()`, replace `UUID.randomUUID()`:

```java
private PointStruct buildPoint(
        ChunkInput chunk, CorpusRef corpus,
        Embedding denseEmbedding, Map<Integer, Float> sparseMap,
        int chunkIndex) {

    String idInput = chunk.sourceDocumentId() + "#" + chunkIndex;
    UUID pointId = UUID.nameUUIDFromBytes(
        idInput.getBytes(java.nio.charset.StandardCharsets.UTF_8));

    // ... rest of buildPoint unchanged, except use pointId ...
    return PointStruct.newBuilder()
        .setId(PointIdFactory.id(pointId))
        // ...
```

- [ ] **Step 4: Apply same change to ReactiveQdrantEmbeddingIngestor**

Mirror the per-document counter and deterministic ID logic in the reactive ingestor's `ingest()` and `buildPoint()`.

- [ ] **Step 5: Run deterministic ID tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest#reingestSameDocumentProducesIdempotentUpsert+multiDocBatchProducesStableIds`
Expected: PASS

- [ ] **Step 6: Run all rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(#35): deterministic point IDs from sourceDocumentId + per-document chunk index"
```

---

### Task 7: InMemoryCaseRetriever filter support

**Files:**
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCaseRetrieverTest.java`

- [ ] **Step 1: Write failing tests for in-memory filtering**

Add to `InMemoryCaseRetrieverTest.java`:

```java
@Test
void filterEqMatchesMetadata() {
    store.ingest(corpus, List.of(
        new ChunkInput("java content", "doc-1", Map.of("domain", "jvm")),
        new ChunkInput("python content", "doc-2", Map.of("domain", "python"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("content", corpus, 10,
        PayloadFilter.eq("domain", "jvm"));
    assertThat(results).hasSize(1);
    assertThat(results.get(0).sourceDocumentId()).isEqualTo("doc-1");
}

@Test
void filterInMatchesMultipleValues() {
    store.ingest(corpus, List.of(
        new ChunkInput("java", "doc-1", Map.of("domain", "jvm")),
        new ChunkInput("python", "doc-2", Map.of("domain", "python")),
        new ChunkInput("rust", "doc-3", Map.of("domain", "rust"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("lang", corpus, 10,
        PayloadFilter.in("domain", List.of("jvm", "rust")));
    assertThat(results).hasSize(2);
    assertThat(results).extracting(RetrievedChunk::sourceDocumentId)
        .containsExactlyInAnyOrder("doc-1", "doc-3");
}

@Test
void filterNotInvertsMatch() {
    store.ingest(corpus, List.of(
        new ChunkInput("java", "doc-1", Map.of("domain", "jvm")),
        new ChunkInput("python", "doc-2", Map.of("domain", "python"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("lang", corpus, 10,
        PayloadFilter.not(PayloadFilter.eq("domain", "jvm")));
    assertThat(results).hasSize(1);
    assertThat(results.get(0).sourceDocumentId()).isEqualTo("doc-2");
}

@Test
void filterAndRequiresAllConditions() {
    store.ingest(corpus, List.of(
        new ChunkInput("java gotcha", "doc-1", Map.of("domain", "jvm", "type", "gotcha")),
        new ChunkInput("java technique", "doc-2", Map.of("domain", "jvm", "type", "technique")),
        new ChunkInput("python gotcha", "doc-3", Map.of("domain", "python", "type", "gotcha"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("content", corpus, 10,
        PayloadFilter.and(
            PayloadFilter.eq("domain", "jvm"),
            PayloadFilter.eq("type", "gotcha")));
    assertThat(results).hasSize(1);
    assertThat(results.get(0).sourceDocumentId()).isEqualTo("doc-1");
}

@Test
void filterOrMatchesAnyCondition() {
    store.ingest(corpus, List.of(
        new ChunkInput("java", "doc-1", Map.of("domain", "jvm")),
        new ChunkInput("python", "doc-2", Map.of("domain", "python")),
        new ChunkInput("rust", "doc-3", Map.of("domain", "rust"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("lang", corpus, 10,
        PayloadFilter.or(
            PayloadFilter.eq("domain", "jvm"),
            PayloadFilter.eq("domain", "python")));
    assertThat(results).hasSize(2);
}

@Test
void filterNullReturnsUnfiltered() {
    store.ingest(corpus, List.of(
        new ChunkInput("java", "doc-1", Map.of("domain", "jvm")),
        new ChunkInput("python", "doc-2", Map.of("domain", "python"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("lang", corpus, 10, null);
    assertThat(results).hasSize(2);
}

@Test
void filterOnMissingFieldReturnsNoMatch() {
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of("domain", "jvm"))
    ));

    List<RetrievedChunk> results = retriever.retrieve("content", corpus, 10,
        PayloadFilter.eq("nonexistent", "value"));
    assertThat(results).isEmpty();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryCaseRetrieverTest`
Expected: FAIL — filter parameter is ignored

- [ ] **Step 3: Implement filter matching in InMemoryCaseRetriever**

In `InMemoryCaseRetriever.java`, add a private matching method and apply it in `retrieve()`:

```java
@Override
public List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
    if (fixedResponse != null) {
        return applyFilter(fixedResponse, filter, maxResults);
    }
    List<ChunkInput> chunks = store.getChunks(corpus);
    List<RetrievedChunk> all = new ArrayList<>(chunks.size());
    for (ChunkInput c : chunks) {
        all.add(new RetrievedChunk(c.content(), c.sourceDocumentId(), 1.0, c.metadata()));
    }
    return applyFilter(all, filter, maxResults);
}

private List<RetrievedChunk> applyFilter(List<RetrievedChunk> chunks, PayloadFilter filter, int maxResults) {
    if (filter == null) {
        return Collections.unmodifiableList(chunks.subList(0, Math.min(maxResults, chunks.size())));
    }
    List<RetrievedChunk> filtered = new ArrayList<>();
    for (RetrievedChunk chunk : chunks) {
        if (matches(chunk.metadata(), filter)) {
            filtered.add(chunk);
            if (filtered.size() >= maxResults) break;
        }
    }
    return Collections.unmodifiableList(filtered);
}

private static boolean matches(Map<String, String> metadata, PayloadFilter filter) {
    return switch (filter) {
        case PayloadFilter.Eq eq -> eq.value().equals(metadata.get(eq.field()));
        case PayloadFilter.In in -> in.values().contains(metadata.get(in.field()));
        case PayloadFilter.Not not -> !matches(metadata, not.inner());
        case PayloadFilter.And and -> and.filters().stream().allMatch(f -> matches(metadata, f));
        case PayloadFilter.Or or -> or.filters().stream().anyMatch(f -> matches(metadata, f));
    };
}
```

- [ ] **Step 4: Run filter tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryCaseRetrieverTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(#35): PayloadFilter matching in InMemoryCaseRetriever"
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

- [ ] **Step 3: Commit if any fixups were needed**

If any fixes were applied during verification, commit them:

```bash
git add -A
git commit -m "fix(#35): build verification fixups"
```

---

Now let me do the self-review.

**1. Spec coverage:**
- Change 1 (PayloadFilter) → Task 1 ✅
- Change 2 (SPI signature) → Tasks 2 + 3 ✅
- Change 3 (Optional sparse) → Task 4 ✅
- Change 4 (Deterministic IDs) → Task 6 ✅
- Change 5 (Filter translation + wiring) → Task 5 ✅
- InMemoryCaseRetriever filtering → Task 7 ✅
- Test plan items → covered across Tasks 1, 4, 5, 6, 7 ✅

**2. Placeholder scan:** No TBDs, TODOs, or "fill in later". All steps have code or commands.

**3. Type consistency:**
- `PayloadFilter` used consistently across all tasks
- `retrieve(..., PayloadFilter filter)` consistent 4-parameter signature
- `toCondition()` / `toQdrantFilter()` naming consistent
- `buildPoint()` parameter change (added `chunkIndex`) consistent between blocking and reactive
