# embedAll Batching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Batch `QdrantEmbeddingIngestor.ingest()` and `ReactiveQdrantEmbeddingIngestor.ingest()` into configurable windows to prevent 400 Bad Request from Ollama on large corpora.

**Architecture:** Extract shared pure logic (`buildPoint`, `computeChunkIndices`) to a package-private `QdrantPointBuilder` utility. Then add a `batchSize` constructor parameter to both Qdrant implementations, splitting embed+upsert into fixed-size windows. Pre-compute per-document chunk indices before the loop so deterministic UUIDs are batch-size-independent.

**Tech Stack:** Java 21, Quarkus 3.32.2, LangChain4j 1.14.1, Qdrant Java client (gRPC), Mutiny (reactive path), Testcontainers (integration tests)

## Global Constraints

- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Test a single module: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag`
- Use `mvn` not `./mvnw`
- All production code in `rag/src/main/java/io/casehub/rag/runtime/`
- All test code in `rag/src/test/java/io/casehub/rag/runtime/`
- Issue: hortora/engine#26

---

## File Map

### Production files

| File | Action | Responsibility |
|------|--------|---------------|
| `rag/src/main/java/io/casehub/rag/runtime/QdrantPointBuilder.java` | **Create** | Package-private utility: `computeChunkIndices()` + `buildPoint()` — pure computation, no I/O |
| `rag/src/main/java/io/casehub/rag/runtime/RagConfig.java` | Modify | Add `embeddingBatchSize()` with default 100 |
| `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java` | Modify | Add `batchSize` field + validation, refactor `ingest()` to batch loop, delegate `buildPoint` to `QdrantPointBuilder` |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java` | Modify | Same — `batchSize` field + validation, `Multi`-based batch loop, delegate `buildPoint` to `QdrantPointBuilder` |
| `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java` | Modify | Pass `config.embeddingBatchSize()` to `QdrantEmbeddingIngestor` constructor |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java` | Modify | Pass `config.embeddingBatchSize()` to `ReactiveQdrantEmbeddingIngestor` constructor |

### Test files

| File | Action | Responsibility |
|------|--------|---------------|
| `rag/src/test/java/io/casehub/rag/runtime/QdrantPointBuilderTest.java` | **Create** | Unit tests for `computeChunkIndices()` and `buildPoint()` — no Testcontainers |
| `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java` | Modify | Add `batchSize` to constructors, add batching integration tests |
| `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java` | Modify | Add `batchSize` to constructors, add batching integration tests |
| `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java` | Modify | Add `batchSize` to 3 `QdrantEmbeddingIngestor` constructor calls |
| `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java` | Modify | Add `batchSize` to 2 `QdrantEmbeddingIngestor` constructor calls |
| `rag/src/test/java/io/casehub/rag/runtime/AssertTenantReactiveTest.java` | Modify | Add `batchSize` to 1 `ReactiveQdrantEmbeddingIngestor` constructor call |

---

### Task 1: Extract QdrantPointBuilder + unit tests

Pure refactoring — extract duplicated logic from both Qdrant implementations into a shared utility. All existing tests must pass unchanged after this task.

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/QdrantPointBuilder.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/QdrantPointBuilderTest.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java:267-311`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java:231-268`

**Interfaces:**
- Produces: `QdrantPointBuilder.computeChunkIndices(List<ChunkInput>)` → `int[]`, `QdrantPointBuilder.buildPoint(ChunkInput, CorpusRef, Embedding, Map<Integer,Float>, int, String, String)` → `PointStruct`

- [ ] **Step 1: Write the failing tests for `computeChunkIndices`**

Create `rag/src/test/java/io/casehub/rag/runtime/QdrantPointBuilderTest.java`:

```java
package io.casehub.rag.runtime;

import io.casehub.rag.ChunkInput;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class QdrantPointBuilderTest {

    @Test
    void computeChunkIndicesEmpty() {
        assertThat(QdrantPointBuilder.computeChunkIndices(List.of())).isEmpty();
    }

    @Test
    void computeChunkIndicesSingleChunk() {
        List<ChunkInput> chunks = List.of(
            new ChunkInput("text", "doc-1", Map.of()));
        assertThat(QdrantPointBuilder.computeChunkIndices(chunks))
            .containsExactly(0);
    }

    @Test
    void computeChunkIndicesAllSameDocument() {
        List<ChunkInput> chunks = List.of(
            new ChunkInput("a", "doc-1", Map.of()),
            new ChunkInput("b", "doc-1", Map.of()),
            new ChunkInput("c", "doc-1", Map.of()));
        assertThat(QdrantPointBuilder.computeChunkIndices(chunks))
            .containsExactly(0, 1, 2);
    }

    @Test
    void computeChunkIndicesAllDifferentDocuments() {
        List<ChunkInput> chunks = List.of(
            new ChunkInput("a", "doc-1", Map.of()),
            new ChunkInput("b", "doc-2", Map.of()),
            new ChunkInput("c", "doc-3", Map.of()));
        assertThat(QdrantPointBuilder.computeChunkIndices(chunks))
            .containsExactly(0, 0, 0);
    }

    @Test
    void computeChunkIndicesInterleavedDocuments() {
        List<ChunkInput> chunks = List.of(
            new ChunkInput("a", "doc-A", Map.of()),
            new ChunkInput("b", "doc-A", Map.of()),
            new ChunkInput("c", "doc-B", Map.of()),
            new ChunkInput("d", "doc-A", Map.of()),
            new ChunkInput("e", "doc-B", Map.of()));
        assertThat(QdrantPointBuilder.computeChunkIndices(chunks))
            .containsExactly(0, 1, 0, 2, 1);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest -Dsurefire.failIfNoSpecifiedTests=false`

Expected: Compilation failure — `QdrantPointBuilder` does not exist.

- [ ] **Step 3: Create `QdrantPointBuilder` with `computeChunkIndices`**

Create `rag/src/main/java/io/casehub/rag/runtime/QdrantPointBuilder.java`:

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.qdrant.client.PointIdFactory;
import io.qdrant.client.ValueFactory;
import io.qdrant.client.VectorFactory;
import io.qdrant.client.VectorsFactory;
import io.qdrant.client.grpc.JsonWithInt.Value;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.Vector;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

final class QdrantPointBuilder {

    private QdrantPointBuilder() {}

    static int[] computeChunkIndices(List<ChunkInput> chunks) {
        int[] indices = new int[chunks.size()];
        Map<String, Integer> counters = new HashMap<>();
        for (int i = 0; i < chunks.size(); i++) {
            String docId = chunks.get(i).sourceDocumentId();
            int idx = counters.getOrDefault(docId, 0);
            indices[i] = idx;
            counters.put(docId, idx + 1);
        }
        return indices;
    }

    static PointStruct buildPoint(
            ChunkInput chunk, CorpusRef corpus,
            Embedding denseEmbedding, Map<Integer, Float> sparseMap,
            int chunkIndex, String denseVectorName, String sparseVectorName) {

        String idInput = chunk.sourceDocumentId() + "#" + chunkIndex;
        UUID pointId = UUID.nameUUIDFromBytes(idInput.getBytes(StandardCharsets.UTF_8));

        Vector denseVector = VectorFactory.vector(denseEmbedding.vectorAsList());

        Map<String, Vector> namedVectors;
        if (sparseMap != null) {
            List<Float> sparseValues = new ArrayList<>(sparseMap.size());
            List<Integer> sparseIndices = new ArrayList<>(sparseMap.size());
            for (Map.Entry<Integer, Float> entry : sparseMap.entrySet()) {
                sparseIndices.add(entry.getKey());
                sparseValues.add(entry.getValue());
            }
            Vector sparseVector = VectorFactory.vector(sparseValues, sparseIndices);
            namedVectors = Map.of(
                denseVectorName, denseVector,
                sparseVectorName, sparseVector);
        } else {
            namedVectors = Map.of(denseVectorName, denseVector);
        }

        Map<String, Value> payload = new HashMap<>();
        payload.put("content", ValueFactory.value(chunk.content()));
        payload.put("sourceDocumentId", ValueFactory.value(chunk.sourceDocumentId()));
        payload.put("tenantId", ValueFactory.value(corpus.tenantId()));
        for (Map.Entry<String, String> meta : chunk.metadata().entrySet()) {
            payload.put(meta.getKey(), ValueFactory.value(meta.getValue()));
        }

        return PointStruct.newBuilder()
            .setId(PointIdFactory.id(pointId))
            .setVectors(VectorsFactory.namedVectors(namedVectors))
            .putAllPayload(payload)
            .build();
    }
}
```

- [ ] **Step 4: Run `computeChunkIndices` tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest`

Expected: All 5 tests PASS.

- [ ] **Step 5: Add `buildPoint` unit tests**

Append to `QdrantPointBuilderTest.java`:

```java
    @Test
    void buildPointDeterministicUuid() {
        ChunkInput chunk = new ChunkInput("text", "doc-1", Map.of());
        Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f, 0.3f});

        PointStruct p1 = QdrantPointBuilder.buildPoint(
            chunk, new CorpusRef("t1", "corpus"), embedding, null, 0, "dense", "sparse");
        PointStruct p2 = QdrantPointBuilder.buildPoint(
            chunk, new CorpusRef("t1", "corpus"), embedding, null, 0, "dense", "sparse");

        assertThat(p1.getId()).isEqualTo(p2.getId());
    }

    @Test
    void buildPointDifferentChunkIndexProducesDifferentUuid() {
        ChunkInput chunk = new ChunkInput("text", "doc-1", Map.of());
        Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f, 0.3f});
        CorpusRef corpus = new CorpusRef("t1", "corpus");

        PointStruct p0 = QdrantPointBuilder.buildPoint(
            chunk, corpus, embedding, null, 0, "dense", "sparse");
        PointStruct p1 = QdrantPointBuilder.buildPoint(
            chunk, corpus, embedding, null, 1, "dense", "sparse");

        assertThat(p0.getId()).isNotEqualTo(p1.getId());
    }

    @Test
    void buildPointDenseOnly() {
        ChunkInput chunk = new ChunkInput("text", "doc-1", Map.of("key", "val"));
        Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f});
        CorpusRef corpus = new CorpusRef("t1", "corpus");

        PointStruct point = QdrantPointBuilder.buildPoint(
            chunk, corpus, embedding, null, 0, "dense", "sparse");

        assertThat(point.getVectors().getVectorsMap()).containsKey("dense");
        assertThat(point.getVectors().getVectorsMap()).doesNotContainKey("sparse");
        assertThat(point.getPayloadMap().get("content").getStringValue()).isEqualTo("text");
        assertThat(point.getPayloadMap().get("sourceDocumentId").getStringValue()).isEqualTo("doc-1");
        assertThat(point.getPayloadMap().get("tenantId").getStringValue()).isEqualTo("t1");
        assertThat(point.getPayloadMap().get("key").getStringValue()).isEqualTo("val");
    }

    @Test
    void buildPointWithSparse() {
        ChunkInput chunk = new ChunkInput("text", "doc-1", Map.of());
        Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f});
        Map<Integer, Float> sparse = Map.of(5, 0.9f, 10, 0.3f);
        CorpusRef corpus = new CorpusRef("t1", "corpus");

        PointStruct point = QdrantPointBuilder.buildPoint(
            chunk, corpus, embedding, sparse, 0, "dense", "sparse");

        assertThat(point.getVectors().getVectorsMap()).containsKey("dense");
        assertThat(point.getVectors().getVectorsMap()).containsKey("sparse");
    }
```

Add this import to the top:

```java
import dev.langchain4j.data.embedding.Embedding;
import io.casehub.rag.CorpusRef;
import io.qdrant.client.grpc.Points.PointStruct;
```

- [ ] **Step 6: Run all `QdrantPointBuilderTest` tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest`

Expected: All 9 tests PASS.

- [ ] **Step 7: Refactor `QdrantEmbeddingIngestor` to delegate to `QdrantPointBuilder`**

In `QdrantEmbeddingIngestor.java`, replace the `ingest()` method body (lines 72-114) with:

```java
    @Override
    public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        tenantGuard.assertTenant(corpus.tenantId());

        String collection = tenancyStrategy.collectionName(corpus);
        ensureCollection(collection);

        List<TextSegment> segments = new ArrayList<>(chunks.size());
        List<String> texts = new ArrayList<>(chunks.size());
        for (ChunkInput chunk : chunks) {
            segments.add(TextSegment.from(chunk.content()));
            texts.add(chunk.content());
        }
        Response<List<Embedding>> denseResponse = embeddingModel.embedAll(segments);
        List<Embedding> denseEmbeddings = denseResponse.content();

        List<Map<Integer, Float>> sparseEmbeddings = sparseEmbedder != null
            ? sparseEmbedder.embedBatch(texts) : null;

        int[] chunkIndices = QdrantPointBuilder.computeChunkIndices(chunks);
        List<PointStruct> points = new ArrayList<>(chunks.size());
        for (int i = 0; i < chunks.size(); i++) {
            points.add(QdrantPointBuilder.buildPoint(chunks.get(i), corpus,
                denseEmbeddings.get(i),
                sparseEmbeddings != null ? sparseEmbeddings.get(i) : null,
                chunkIndices[i], denseVectorName, sparseVectorName));
        }

        try {
            client.upsertAsync(collection, points).get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted during upsert", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Upsert failed", e.getCause());
        }
    }
```

Delete the private `buildPoint()` method (lines 267-311).

- [ ] **Step 8: Refactor `ReactiveQdrantEmbeddingIngestor` to delegate to `QdrantPointBuilder`**

In `ReactiveQdrantEmbeddingIngestor.java`, replace the point-building section of `ingest()` (lines 97-111) with:

```java
            .chain(embeddings -> {
                int[] chunkIndices = QdrantPointBuilder.computeChunkIndices(chunks);
                List<PointStruct> points = new ArrayList<>(chunks.size());
                for (int i = 0; i < chunks.size(); i++) {
                    points.add(QdrantPointBuilder.buildPoint(chunks.get(i), corpus,
                        embeddings.dense().get(i),
                        embeddings.sparse() != null ? embeddings.sparse().get(i) : null,
                        chunkIndices[i], denseVectorName, sparseVectorName));
                }
                return QdrantFutures.toUni(client.upsertAsync(collection, points))
                    .replaceWithVoid();
            });
```

Delete the private `buildPoint()` method (lines 231-267).

- [ ] **Step 9: Run all existing tests to verify refactoring is safe**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: ALL existing tests PASS. This is a pure refactoring — behaviour is identical.

- [ ] **Step 10: Commit**

```
git add rag/src/main/java/io/casehub/rag/runtime/QdrantPointBuilder.java rag/src/test/java/io/casehub/rag/runtime/QdrantPointBuilderTest.java rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java
git commit -m "refactor(engine#26): extract QdrantPointBuilder — shared buildPoint + computeChunkIndices"
```

---

### Task 2: Batching implementation — blocking + reactive + config + tests

Add `batchSize` to both Qdrant implementations, implement batch loops, update config and producers, update all test constructor calls, add batching integration tests.

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagConfig.java:8-52`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java:42-114`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java:46-113`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java:31-38`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java:43-48`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/AssertTenantReactiveTest.java`

**Interfaces:**
- Consumes: `QdrantPointBuilder.computeChunkIndices()`, `QdrantPointBuilder.buildPoint()` from Task 1
- Produces: `RagConfig.embeddingBatchSize()` → `int` (default 100)

- [ ] **Step 1: Add `embeddingBatchSize()` to `RagConfig`**

In `rag/src/main/java/io/casehub/rag/runtime/RagConfig.java`, add after line 21 (`retrieval()` method):

```java

    @WithDefault("100")
    int embeddingBatchSize();
```

- [ ] **Step 2: Add `batchSize` to `QdrantEmbeddingIngestor` constructor**

In `QdrantEmbeddingIngestor.java`:

Add field after `tenantGuard` (line 50):

```java
    private final int batchSize;
```

Add `int batchSize` as the last constructor parameter. Add validation as the first line of the constructor body:

```java
    QdrantEmbeddingIngestor(
            QdrantClient client,
            EmbeddingModel embeddingModel,
            SparseEmbedder sparseEmbedder,
            TenancyStrategy tenancyStrategy,
            String denseVectorName,
            String sparseVectorName,
            TenantGuard tenantGuard,
            int batchSize) {
        if (batchSize <= 0) {
            throw new IllegalArgumentException("batchSize must be positive, got: " + batchSize);
        }
        this.client = client;
        this.embeddingModel = embeddingModel;
        this.sparseEmbedder = sparseEmbedder;
        this.tenancyStrategy = tenancyStrategy;
        this.denseVectorName = denseVectorName;
        this.sparseVectorName = sparseVectorName;
        this.tenantGuard = tenantGuard;
        this.batchSize = batchSize;
    }
```

Add a `private static final Logger`:

```java
    private static final Logger LOG = Logger.getLogger(QdrantEmbeddingIngestor.class.getName());
```

Add import: `import java.util.logging.Logger;`

- [ ] **Step 3: Add `batchSize` to `ReactiveQdrantEmbeddingIngestor` constructor**

In `ReactiveQdrantEmbeddingIngestor.java`:

Add field after `tenantGuard` (line 55):

```java
    private final int batchSize;
```

Add `int batchSize` as the last constructor parameter. Add validation:

```java
    ReactiveQdrantEmbeddingIngestor(
            QdrantClient client,
            EmbeddingModel embeddingModel,
            SparseEmbedder sparseEmbedder,
            TenancyStrategy tenancyStrategy,
            String denseVectorName,
            String sparseVectorName,
            int denseDimension,
            TenantGuard tenantGuard,
            int batchSize) {
        if (batchSize <= 0) {
            throw new IllegalArgumentException("batchSize must be positive, got: " + batchSize);
        }
        this.client = client;
        this.embeddingModel = embeddingModel;
        this.sparseEmbedder = sparseEmbedder;
        this.tenancyStrategy = tenancyStrategy;
        this.denseVectorName = denseVectorName;
        this.sparseVectorName = sparseVectorName;
        this.denseDimension = denseDimension;
        this.tenantGuard = tenantGuard;
        this.batchSize = batchSize;
    }
```

Add a `private static final Logger`:

```java
    private static final Logger LOG = Logger.getLogger(ReactiveQdrantEmbeddingIngestor.class.getName());
```

Add import: `import java.util.logging.Logger;`

- [ ] **Step 4: Update `RagBeanProducer` to pass config**

In `RagBeanProducer.java`, change the `corpusStore()` method to pass `config.embeddingBatchSize()` as the last constructor argument:

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
            tenantGuard,
            config.embeddingBatchSize());
    }
```

- [ ] **Step 5: Update `ReactiveRagBeanProducer` to pass config**

In `ReactiveRagBeanProducer.java`, change the `corpusStore()` method to pass `config.embeddingBatchSize()` as the last constructor argument:

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
            denseDimension, tenantGuard,
            config.embeddingBatchSize());
    }
```

- [ ] **Step 6: Update all test constructor calls — add `batchSize` as last argument**

In every `new QdrantEmbeddingIngestor(...)` call in test files, add `Integer.MAX_VALUE` as the last argument (preserves existing unbatched behaviour). All 8 call sites:

**`QdrantEmbeddingIngestorTest.java`** — 3 sites:
- Line 59: `store = new QdrantEmbeddingIngestor(... tenantGuard)` → add `, Integer.MAX_VALUE)`
- Line 169: `new QdrantEmbeddingIngestor(... "sparse",` → add `Integer.MAX_VALUE` after `TenantGuard`
- Line 229: `new QdrantEmbeddingIngestor(... TenantGuard.of(null))` → add `, Integer.MAX_VALUE)`

**`HybridCaseRetrieverTest.java`** — 3 sites:
- Line 66: add `, Integer.MAX_VALUE)` after `guard`
- Line 146: add `, Integer.MAX_VALUE)` after `denseOnlyGuard`
- Line 204: add `, Integer.MAX_VALUE)` after `noTenantGuard`

**`ReactiveHybridCaseRetrieverTest.java`** — 2 sites:
- Line 62: add `, Integer.MAX_VALUE)` after `guard`
- Line 142: add `, Integer.MAX_VALUE)` after `noTenantGuard`

In every `new ReactiveQdrantEmbeddingIngestor(...)` call, add `Integer.MAX_VALUE` as the last argument. All 3 call sites:

**`ReactiveQdrantEmbeddingIngestorTest.java`** — 2 sites:
- Line 55: add `, Integer.MAX_VALUE)` after `TenantGuard`
- Line 172: add `, Integer.MAX_VALUE)` after `TenantGuard`

**`AssertTenantReactiveTest.java`** — 1 site:
- Line 79: add `, Integer.MAX_VALUE)` after `RagTestFixtures.stubPrincipal(TENANT))`

- [ ] **Step 7: Verify all existing tests still pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: ALL tests PASS. The `Integer.MAX_VALUE` batch size means the loop executes exactly once — identical to pre-batching behaviour.

- [ ] **Step 8: Write failing batching tests for blocking ingestor**

Append to `QdrantEmbeddingIngestorTest.java`:

```java
    @Test
    void ingestBatchesSplitCorrectly() {
        // batchSize=2, 5 chunks → 3 batches (2+2+1)
        QdrantEmbeddingIngestor batchedStore = new QdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            new SparseEmbedder(InMemoryInferenceModel.returning(
                0.5f, 0.0f, 0.3f, 0.0f, 0.8f, 0.0f, 0.0f, 0.2f)),
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse",
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            2);

        CorpusRef corpus = uniqueCorpus();
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("chunk 1", "doc-1", Map.of()),
            new ChunkInput("chunk 2", "doc-1", Map.of()),
            new ChunkInput("chunk 3", "doc-2", Map.of()),
            new ChunkInput("chunk 4", "doc-2", Map.of()),
            new ChunkInput("chunk 5", "doc-1", Map.of())));

        assertThat(batchedStore.listDocuments(corpus))
            .containsExactlyInAnyOrder("doc-1", "doc-2");
    }

    @Test
    void ingestCrossBatchDocumentContinuity() {
        // doc-A has chunks in both batch 1 and batch 2 — indices must be continuous
        QdrantEmbeddingIngestor batchedStore = new QdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            null, // dense-only for simplicity
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse",
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            2);

        CorpusRef corpus = uniqueCorpus();
        // Batch 1: [A#0, A#1], Batch 2: [A#2]
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("a0", "doc-A", Map.of()),
            new ChunkInput("a1", "doc-A", Map.of()),
            new ChunkInput("a2", "doc-A", Map.of())));

        assertThat(batchedStore.listDocuments(corpus)).containsExactly("doc-A");

        // Re-ingest with same content — idempotent, no duplicates
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("a0", "doc-A", Map.of()),
            new ChunkInput("a1", "doc-A", Map.of()),
            new ChunkInput("a2", "doc-A", Map.of())));

        assertThat(batchedStore.listDocuments(corpus)).containsExactly("doc-A");
    }

    @Test
    void ingestBatchSizeOne() {
        QdrantEmbeddingIngestor batchedStore = new QdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            null,
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse",
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            1);

        CorpusRef corpus = uniqueCorpus();
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("chunk 1", "doc-1", Map.of()),
            new ChunkInput("chunk 2", "doc-2", Map.of()),
            new ChunkInput("chunk 3", "doc-1", Map.of())));

        assertThat(batchedStore.listDocuments(corpus))
            .containsExactlyInAnyOrder("doc-1", "doc-2");
    }

    @Test
    void constructorRejectsBatchSizeZero() {
        assertThatThrownBy(() -> new QdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            null,
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse",
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            0))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("batchSize");
    }
```

- [ ] **Step 9: Run new blocking tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest#ingestBatchesSplitCorrectly+ingestCrossBatchDocumentContinuity+ingestBatchSizeOne+constructorRejectsBatchSizeZero`

Expected: `constructorRejectsBatchSizeZero` PASSES (validation already added). The other 3 FAIL — `ingest()` still processes in one shot regardless of `batchSize` (it's unused).

- [ ] **Step 10: Implement batch loop in `QdrantEmbeddingIngestor.ingest()`**

Replace the `ingest()` method body:

```java
    @Override
    public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        tenantGuard.assertTenant(corpus.tenantId());
        if (chunks.isEmpty()) return;

        String collection = tenancyStrategy.collectionName(corpus);
        ensureCollection(collection);

        int[] chunkIndices = QdrantPointBuilder.computeChunkIndices(chunks);
        int totalBatches = (chunks.size() + batchSize - 1) / batchSize;

        for (int batchNum = 0; batchNum < totalBatches; batchNum++) {
            int start = batchNum * batchSize;
            int end = Math.min(start + batchSize, chunks.size());
            List<ChunkInput> batch = chunks.subList(start, end);

            List<TextSegment> segments = new ArrayList<>(batch.size());
            List<String> texts = new ArrayList<>(batch.size());
            for (ChunkInput chunk : batch) {
                segments.add(TextSegment.from(chunk.content()));
                texts.add(chunk.content());
            }
            Response<List<Embedding>> denseResponse = embeddingModel.embedAll(segments);
            List<Embedding> denseEmbeddings = denseResponse.content();

            List<Map<Integer, Float>> sparseEmbeddings = sparseEmbedder != null
                ? sparseEmbedder.embedBatch(texts) : null;

            List<PointStruct> points = new ArrayList<>(batch.size());
            for (int i = 0; i < batch.size(); i++) {
                points.add(QdrantPointBuilder.buildPoint(batch.get(i), corpus,
                    denseEmbeddings.get(i),
                    sparseEmbeddings != null ? sparseEmbeddings.get(i) : null,
                    chunkIndices[start + i], denseVectorName, sparseVectorName));
            }

            try {
                client.upsertAsync(collection, points).get();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("Interrupted during upsert", e);
            } catch (ExecutionException e) {
                throw new RuntimeException("Upsert failed", e.getCause());
            }

            LOG.fine(() -> "Ingested batch " + (batchNum + 1) + "/" + totalBatches
                + " (" + end + "/" + chunks.size() + " chunks)");
        }
    }
```

- [ ] **Step 11: Run all blocking tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest`

Expected: ALL tests PASS — both existing tests (with `Integer.MAX_VALUE`) and new batching tests.

- [ ] **Step 12: Write failing batching tests for reactive ingestor**

Append to `ReactiveQdrantEmbeddingIngestorTest.java`:

```java
    @Test
    void ingestBatchesSplitCorrectly() {
        ReactiveQdrantEmbeddingIngestor batchedStore = new ReactiveQdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            new SparseEmbedder(InMemoryInferenceModel.returning(
                0.5f, 0.0f, 0.3f, 0.0f, 0.8f, 0.0f, 0.0f, 0.2f)),
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse", DENSE_DIM,
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            2);

        CorpusRef corpus = uniqueCorpus();
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("chunk 1", "doc-1", Map.of()),
            new ChunkInput("chunk 2", "doc-1", Map.of()),
            new ChunkInput("chunk 3", "doc-2", Map.of()),
            new ChunkInput("chunk 4", "doc-2", Map.of()),
            new ChunkInput("chunk 5", "doc-1", Map.of())))
            .await().indefinitely();

        List<String> docs = batchedStore.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactlyInAnyOrder("doc-1", "doc-2");
    }

    @Test
    void ingestCrossBatchDocumentContinuity() {
        ReactiveQdrantEmbeddingIngestor batchedStore = new ReactiveQdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            null,
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse", DENSE_DIM,
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            2);

        CorpusRef corpus = uniqueCorpus();
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("a0", "doc-A", Map.of()),
            new ChunkInput("a1", "doc-A", Map.of()),
            new ChunkInput("a2", "doc-A", Map.of())))
            .await().indefinitely();

        List<String> docs = batchedStore.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactly("doc-A");

        batchedStore.ingest(corpus, List.of(
            new ChunkInput("a0", "doc-A", Map.of()),
            new ChunkInput("a1", "doc-A", Map.of()),
            new ChunkInput("a2", "doc-A", Map.of())))
            .await().indefinitely();

        docs = batchedStore.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactly("doc-A");
    }

    @Test
    void ingestBatchSizeOne() {
        ReactiveQdrantEmbeddingIngestor batchedStore = new ReactiveQdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            null,
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse", DENSE_DIM,
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            1);

        CorpusRef corpus = uniqueCorpus();
        batchedStore.ingest(corpus, List.of(
            new ChunkInput("chunk 1", "doc-1", Map.of()),
            new ChunkInput("chunk 2", "doc-2", Map.of()),
            new ChunkInput("chunk 3", "doc-1", Map.of())))
            .await().indefinitely();

        List<String> docs = batchedStore.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactlyInAnyOrder("doc-1", "doc-2");
    }

    @Test
    void constructorRejectsBatchSizeZero() {
        assertThatThrownBy(() -> new ReactiveQdrantEmbeddingIngestor(
            client,
            new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
            null,
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse", DENSE_DIM,
            TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
            0))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("batchSize");
    }
```

- [ ] **Step 13: Run new reactive tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveQdrantEmbeddingIngestorTest#ingestBatchesSplitCorrectly+ingestCrossBatchDocumentContinuity+ingestBatchSizeOne+constructorRejectsBatchSizeZero`

Expected: `constructorRejectsBatchSizeZero` PASSES. The other 3 FAIL.

- [ ] **Step 14: Implement batch loop in `ReactiveQdrantEmbeddingIngestor.ingest()`**

Replace the `ingest()` method body. Add import `import io.smallrye.mutiny.Multi;`:

```java
    @Override
    public Uni<Void> ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        return Uni.createFrom().deferred(() -> {
            tenantGuard.assertTenant(corpus.tenantId());
            if (chunks.isEmpty()) return Uni.createFrom().voidItem();

            String collection = tenancyStrategy.collectionName(corpus);
            int[] chunkIndices = QdrantPointBuilder.computeChunkIndices(chunks);
            int totalBatches = (chunks.size() + batchSize - 1) / batchSize;

            List<int[]> batchRanges = new ArrayList<>(totalBatches);
            for (int b = 0; b < totalBatches; b++) {
                int start = b * batchSize;
                int end = Math.min(start + batchSize, chunks.size());
                batchRanges.add(new int[]{b, start, end});
            }

            return ensureCollection(collection)
                .chain(() -> Multi.createFrom().iterable(batchRanges)
                    .onItem().transformToUniAndConcatenate(range -> {
                        int batchNum = range[0];
                        int start = range[1];
                        int end = range[2];
                        List<ChunkInput> batch = chunks.subList(start, end);

                        return Uni.createFrom().item(() -> {
                            List<TextSegment> segments = new ArrayList<>(batch.size());
                            List<String> texts = new ArrayList<>(batch.size());
                            for (ChunkInput chunk : batch) {
                                segments.add(TextSegment.from(chunk.content()));
                                texts.add(chunk.content());
                            }
                            Response<List<Embedding>> denseResponse = embeddingModel.embedAll(segments);
                            List<Map<Integer, Float>> sparseEmbeddings = sparseEmbedder != null
                                ? sparseEmbedder.embedBatch(texts) : null;
                            return new EmbeddingResult(denseResponse.content(), sparseEmbeddings);
                        }).runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
                        .chain(embeddings -> {
                            List<PointStruct> points = new ArrayList<>(batch.size());
                            for (int i = 0; i < batch.size(); i++) {
                                points.add(QdrantPointBuilder.buildPoint(batch.get(i), corpus,
                                    embeddings.dense().get(i),
                                    embeddings.sparse() != null ? embeddings.sparse().get(i) : null,
                                    chunkIndices[start + i], denseVectorName, sparseVectorName));
                            }
                            return QdrantFutures.toUni(client.upsertAsync(collection, points))
                                .invoke(() -> LOG.fine(() -> "Ingested batch " + (batchNum + 1) + "/" + totalBatches
                                    + " (" + end + "/" + chunks.size() + " chunks)"))
                                .replaceWithVoid();
                        });
                    })
                    .collect().last()
                    .replaceWithVoid());
        });
    }
```

- [ ] **Step 15: Run all reactive tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveQdrantEmbeddingIngestorTest`

Expected: ALL tests PASS.

- [ ] **Step 16: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: ALL tests PASS across all test classes.

- [ ] **Step 17: Commit**

```
git add rag/src/main/java/io/casehub/rag/runtime/RagConfig.java rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java rag/src/test/java/io/casehub/rag/runtime/AssertTenantReactiveTest.java
git commit -m "feat(engine#26): batch embedAll into configurable windows — default 100"
```

- [ ] **Step 18: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: BUILD SUCCESS. All modules compile and all tests pass.
