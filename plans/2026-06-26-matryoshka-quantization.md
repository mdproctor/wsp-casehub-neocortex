# Matryoshka Embeddings + Qdrant Quantization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in Matryoshka embedding truncation and Qdrant quantization (binary/scalar) to the RAG pipeline for memory reduction across tenants.

**Architecture:** An `EmbeddingModel` decorator truncates embeddings to configurable dimensions. Qdrant quantization config (binary/scalar) is applied to dense vector params at collection creation. Search-time oversampling is applied to the dense search leg when quantization is active. All features are opt-in via `casehub.rag.*` config properties.

**Tech Stack:** Java 21, Quarkus 3.32.2, LangChain4j 1.14.1, Qdrant Java client 1.18.1, Testcontainers

## Global Constraints

- Java 21 source level, Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build command: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag`
- Test command: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ClassName`
- Use `mvn` not `./mvnw`
- All changes confined to `rag` module — no `rag-api`, `inference-*`, or other module changes
- Existing constructor signatures are package-private — caller migration is within the module only
- Qdrant Testcontainers image: `qdrant/qdrant:v1.18.0`
- Issue: casehubio/neural-text#31

---

### Task 1: MatryoshkaEmbeddingModel decorator

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/MatryoshkaEmbeddingModel.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/MatryoshkaEmbeddingModelTest.java`

**Interfaces:**
- Consumes: `dev.langchain4j.model.embedding.EmbeddingModel`, `dev.langchain4j.data.embedding.Embedding`
- Produces: `MatryoshkaEmbeddingModel` — used by `RagBeanProducer` (Task 5) via `effectiveEmbeddingModel()`

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class MatryoshkaEmbeddingModelTest {

    @Test
    void truncatesEmbeddingToTargetDimension() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);
        MatryoshkaEmbeddingModel model = new MatryoshkaEmbeddingModel(delegate, 4);

        Embedding result = model.embed("test").content();

        assertThat(result.dimension()).isEqualTo(4);
    }

    @Test
    void outputIsL2Normalized() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);
        MatryoshkaEmbeddingModel model = new MatryoshkaEmbeddingModel(delegate, 4);

        Embedding result = model.embed("test").content();

        double norm = 0;
        for (float f : result.vector()) norm += f * f;
        assertThat(Math.sqrt(norm)).isCloseTo(1.0, within(1e-6));
    }

    @Test
    void dimensionReturnsTargetDimension() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);
        MatryoshkaEmbeddingModel model = new MatryoshkaEmbeddingModel(delegate, 4);

        assertThat(model.dimension()).isEqualTo(4);
    }

    @Test
    void modelNameIncludesMatryoshkaSuffix() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);
        MatryoshkaEmbeddingModel model = new MatryoshkaEmbeddingModel(delegate, 4);

        assertThat(model.modelName()).isEqualTo("unknown/matryoshka-4");
    }

    @Test
    void embedAllTruncatesEveryEmbedding() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);
        MatryoshkaEmbeddingModel model = new MatryoshkaEmbeddingModel(delegate, 4);

        Response<List<Embedding>> response = model.embedAll(List.of(
            TextSegment.from("a"), TextSegment.from("b"), TextSegment.from("c")));

        assertThat(response.content()).hasSize(3);
        response.content().forEach(e -> assertThat(e.dimension()).isEqualTo(4));
    }

    @Test
    void rejectsTargetDimensionGreaterThanDelegate() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(4);

        assertThatThrownBy(() -> new MatryoshkaEmbeddingModel(delegate, 8))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsTargetDimensionZero() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);

        assertThatThrownBy(() -> new MatryoshkaEmbeddingModel(delegate, 0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsTargetDimensionNegative() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(8);

        assertThatThrownBy(() -> new MatryoshkaEmbeddingModel(delegate, -1))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void equalDimensionStillNormalizes() {
        EmbeddingModel delegate = new RagTestFixtures.StubEmbeddingModel(4);
        MatryoshkaEmbeddingModel model = new MatryoshkaEmbeddingModel(delegate, 4);

        Embedding result = model.embed("test").content();

        assertThat(result.dimension()).isEqualTo(4);
        double norm = 0;
        for (float f : result.vector()) norm += f * f;
        assertThat(Math.sqrt(norm)).isCloseTo(1.0, within(1e-6));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=MatryoshkaEmbeddingModelTest`

Expected: Compilation failure — `MatryoshkaEmbeddingModel` does not exist.

- [ ] **Step 3: Implement MatryoshkaEmbeddingModel**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class MatryoshkaEmbeddingModel implements EmbeddingModel {

    private final EmbeddingModel delegate;
    private final int targetDimension;

    public MatryoshkaEmbeddingModel(EmbeddingModel delegate, int targetDimension) {
        if (targetDimension <= 0) {
            throw new IllegalArgumentException(
                "targetDimension must be positive, got: " + targetDimension);
        }
        if (targetDimension > delegate.dimension()) {
            throw new IllegalArgumentException(
                "targetDimension (" + targetDimension + ") exceeds delegate dimension ("
                    + delegate.dimension() + ")");
        }
        this.delegate = delegate;
        this.targetDimension = targetDimension;
    }

    @Override
    public Response<List<Embedding>> embedAll(List<TextSegment> textSegments) {
        Response<List<Embedding>> response = delegate.embedAll(textSegments);
        List<Embedding> truncated = new ArrayList<>(response.content().size());
        for (Embedding embedding : response.content()) {
            truncated.add(truncateAndNormalize(embedding));
        }
        return Response.from(truncated, response.tokenUsage(), response.finishReason());
    }

    @Override
    public int dimension() {
        return targetDimension;
    }

    @Override
    public String modelName() {
        return delegate.modelName() + "/matryoshka-" + targetDimension;
    }

    private Embedding truncateAndNormalize(Embedding embedding) {
        float[] truncated = Arrays.copyOf(embedding.vector(), targetDimension);
        double norm = 0;
        for (float f : truncated) {
            norm += f * f;
        }
        norm = Math.sqrt(norm);
        if (norm > 1e-10) {
            for (int i = 0; i < truncated.length; i++) {
                truncated[i] /= (float) norm;
            }
        }
        return Embedding.from(truncated);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=MatryoshkaEmbeddingModelTest`

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/MatryoshkaEmbeddingModel.java rag/src/test/java/io/casehub/rag/runtime/MatryoshkaEmbeddingModelTest.java
```

Message: `feat(#31): MatryoshkaEmbeddingModel — truncating EmbeddingModel decorator`

---

### Task 2: DenseQuantization enum + RagConfig extensions

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/DenseQuantization.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagConfig.java`

**Interfaces:**
- Consumes: nothing
- Produces: `DenseQuantization` enum, `RagConfig.MatryoshkaConfig`, `RagConfig.QuantizationConfig` — used by all subsequent tasks

- [ ] **Step 1: Create DenseQuantization enum**

```java
package io.casehub.rag.runtime;

public enum DenseQuantization {
    NONE,
    BINARY,
    SCALAR
}
```

- [ ] **Step 2: Add config interfaces to RagConfig**

Add these interfaces inside `RagConfig`, after the existing `RetrievalConfig`:

```java
MatryoshkaConfig matryoshka();

interface MatryoshkaConfig {
    OptionalInt dimension();
}

QuantizationConfig quantization();

interface QuantizationConfig {
    @WithDefault("NONE")
    DenseQuantization type();

    @WithDefault("true")
    boolean alwaysRam();

    OptionalDouble oversampling();
}
```

Add `import java.util.OptionalDouble;` and `import java.util.OptionalInt;` to the imports.

- [ ] **Step 3: Verify build compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`

Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/DenseQuantization.java rag/src/main/java/io/casehub/rag/runtime/RagConfig.java
```

Message: `feat(#31): DenseQuantization enum + RagConfig matryoshka/quantization groups`

---

### Task 3: Ingestor quantization + dimension validation

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java`

**Interfaces:**
- Consumes: `DenseQuantization` enum (Task 2), `RagConfig.QuantizationConfig` (Task 2)
- Produces: Updated `QdrantEmbeddingIngestor` and `ReactiveQdrantEmbeddingIngestor` constructors — used by producers (Task 5)

- [ ] **Step 1: Write failing test for quantization config in blocking ingestor**

Add to `QdrantEmbeddingIngestorTest`:

```java
@Test
void ensureCollectionAppliesBinaryQuantization() throws Exception {
    QdrantEmbeddingIngestor quantizedStore = new QdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        Integer.MAX_VALUE,
        DenseQuantization.BINARY, true
    );

    CorpusRef corpus = uniqueCorpus();
    quantizedStore.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    var info = client.getCollectionInfoAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get();
    var denseParams = info.getConfig().getParams().getVectorsConfig()
        .getParamsMap().getMapMap().get("dense");
    assertThat(denseParams.hasQuantizationConfig()).isTrue();
    assertThat(denseParams.getQuantizationConfig().hasBinary()).isTrue();
    assertThat(denseParams.getQuantizationConfig().getBinary().getAlwaysRam()).isTrue();
}

@Test
void ensureCollectionAppliesScalarQuantization() throws Exception {
    QdrantEmbeddingIngestor quantizedStore = new QdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        Integer.MAX_VALUE,
        DenseQuantization.SCALAR, true
    );

    CorpusRef corpus = uniqueCorpus();
    quantizedStore.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    var info = client.getCollectionInfoAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get();
    var denseParams = info.getConfig().getParams().getVectorsConfig()
        .getParamsMap().getMapMap().get("dense");
    assertThat(denseParams.hasQuantizationConfig()).isTrue();
    assertThat(denseParams.getQuantizationConfig().hasScalar()).isTrue();
}

@Test
void ensureCollectionNoQuantizationByDefault() throws Exception {
    // Existing store uses DenseQuantization.NONE
    CorpusRef corpus = uniqueCorpus();
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    var info = client.getCollectionInfoAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get();
    var denseParams = info.getConfig().getParams().getVectorsConfig()
        .getParamsMap().getMapMap().get("dense");
    assertThat(denseParams.hasQuantizationConfig()).isFalse();
}

@Test
void ensureCollectionRejectsDimensionMismatch() {
    // Create collection with dim=4 (via existing store)
    CorpusRef corpus = uniqueCorpus();
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    // Try to ingest with dim=2 — should fail with dimension mismatch
    QdrantEmbeddingIngestor wrongDimStore = new QdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(2),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        Integer.MAX_VALUE,
        DenseQuantization.NONE, true
    );

    assertThatThrownBy(() -> wrongDimStore.ingest(corpus, List.of(
        new ChunkInput("content", "doc-2", Map.of()))))
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("dimension");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest`

Expected: Compilation failure — constructor doesn't accept `DenseQuantization` + `boolean` params yet.

- [ ] **Step 3: Implement blocking ingestor changes**

Modify `QdrantEmbeddingIngestor`:

1. Add fields: `private final DenseQuantization quantizationType;` and `private final boolean alwaysRam;`

2. Add constructor parameters after `int batchSize`: `DenseQuantization quantizationType, boolean alwaysRam`

3. Store fields in constructor body (after `this.batchSize = batchSize;`):
   ```java
   this.quantizationType = quantizationType;
   this.alwaysRam = alwaysRam;
   ```

4. In `ensureCollection()`, after `if (client.collectionExistsAsync(collection).get())`, replace the simple `knownCollections.add(collection); return;` with a dimension validation check:
   ```java
   if (client.collectionExistsAsync(collection).get()) {
       var info = client.getCollectionInfoAsync(collection).get();
       int existingDim = (int) info.getConfig().getParams().getVectorsConfig()
           .getParamsMap().getMapMap().get(denseVectorName).getSize();
       int configuredDim = embeddingModel.dimension();
       if (existingDim != configuredDim) {
           throw new IllegalStateException(
               "Configured embedding dimension (" + configuredDim
                   + ") does not match existing collection dimension (" + existingDim
                   + ") for collection '" + collection
                   + "'. Re-index the collection or adjust matryoshka.dimension.");
       }
       knownCollections.add(collection);
       return;
   }
   ```

5. After building `denseParams`, add quantization config before `.build()`:
   ```java
   VectorParams.Builder denseParamsBuilder = VectorParams.newBuilder()
       .setSize(embeddingModel.dimension())
       .setDistance(Distance.Cosine);

   if (quantizationType == DenseQuantization.BINARY) {
       denseParamsBuilder.setQuantizationConfig(
           io.qdrant.client.grpc.Collections.QuantizationConfig.newBuilder()
               .setBinary(io.qdrant.client.grpc.Collections.BinaryQuantization.newBuilder()
                   .setAlwaysRam(alwaysRam)
                   .build())
               .build());
   } else if (quantizationType == DenseQuantization.SCALAR) {
       denseParamsBuilder.setQuantizationConfig(
           io.qdrant.client.grpc.Collections.QuantizationConfig.newBuilder()
               .setScalar(io.qdrant.client.grpc.Collections.ScalarQuantization.newBuilder()
                   .setType(io.qdrant.client.grpc.Collections.QuantizationType.Int8)
                   .setAlwaysRam(alwaysRam)
                   .build())
               .build());
   }

   VectorParams denseParams = denseParamsBuilder.build();
   ```

   Add import: `import io.qdrant.client.grpc.Collections.GetCollectionInfoResponse;`

6. Update the existing `setUp()` in tests to pass `DenseQuantization.NONE, true` to all existing constructor calls.

- [ ] **Step 4: Run blocking ingestor tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest`

Expected: All tests PASS (existing + new).

- [ ] **Step 5: Implement reactive ingestor changes**

Modify `ReactiveQdrantEmbeddingIngestor`:

1. Add fields: `private final DenseQuantization quantizationType;` and `private final boolean alwaysRam;`

2. Remove `int denseDimension` from constructor parameters. Add `DenseQuantization quantizationType, boolean alwaysRam` after `String sparseVectorName`.

3. In constructor body, compute dimension from the model:
   ```java
   this.denseDimension = embeddingModel.dimension();
   this.quantizationType = quantizationType;
   this.alwaysRam = alwaysRam;
   ```

4. In `buildCreateRequest()`, apply the same quantization config as the blocking ingestor (same pattern — switch on `quantizationType`).

5. In `ensureCollection()`, add dimension validation after `collectionExistsAsync()` returns true (same pattern as blocking, but using `QdrantFutures.toUni()` for the `getCollectionInfoAsync` call):
   ```java
   return QdrantFutures.<Boolean>toUni(client.collectionExistsAsync(k))
       .chain(exists -> {
           if (exists) {
               return QdrantFutures.toUni(client.getCollectionInfoAsync(k))
                   .invoke(info -> {
                       int existingDim = (int) info.getConfig().getParams()
                           .getVectorsConfig().getParamsMap().getMapMap()
                           .get(denseVectorName).getSize();
                       if (existingDim != denseDimension) {
                           throw new IllegalStateException(
                               "Configured embedding dimension (" + denseDimension
                                   + ") does not match existing collection dimension ("
                                   + existingDim + ") for collection '" + k
                                   + "'. Re-index the collection or adjust matryoshka.dimension.");
                       }
                   })
                   .replaceWithVoid();
           }
           return QdrantFutures.toUni(
               client.createCollectionAsync(buildCreateRequest(k)))
               .replaceWithVoid();
       })
   ```

6. Update `ReactiveQdrantEmbeddingIngestorTest.setUp()`: remove the `DENSE_DIM` argument from the constructor call, add `DenseQuantization.NONE, true` after `"sparse"`.

- [ ] **Step 6: Run reactive ingestor tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveQdrantEmbeddingIngestorTest`

Expected: All tests PASS.

- [ ] **Step 7: Run full rag test suite to check for compilation breaks in other tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: Compilation failures in `HybridCaseRetrieverTest`, `ReactiveHybridCaseRetrieverTest`, and producer tests that construct ingestors with the old signature. These will be fixed in Tasks 4 and 5. For now, verify the ingestor tests pass and note the expected compilation failures.

If other test classes fail to compile, add `DenseQuantization.NONE, true` to their constructor calls now.

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java
```

Message: `feat(#31): ingestor quantization config + dimension validation`

---

### Task 4: Retriever search-time oversampling

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `DenseQuantization` enum (Task 2)
- Produces: Updated `HybridCaseRetriever` and `ReactiveHybridCaseRetriever` constructors — used by producers (Task 5)

- [ ] **Step 1: Write failing test for oversampling in blocking retriever**

Add to `HybridCaseRetrieverTest`:

```java
@Test
void quantizedRetrieverIngestsAndRetrieves() {
    // Verify end-to-end: quantized ingestor + retriever work together
    EmbeddingModel model = new RagTestFixtures.StubEmbeddingModel(DENSE_DIM);
    TenantGuard guard = TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT));

    QdrantEmbeddingIngestor quantizedStore = new QdrantEmbeddingIngestor(
        client, model, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        guard, Integer.MAX_VALUE,
        DenseQuantization.BINARY, true
    );

    HybridCaseRetriever quantizedRetriever = new HybridCaseRetriever(
        client, model, null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME,
        64, 64, 60,
        false, 10, null,
        guard,
        DenseQuantization.BINARY, java.util.OptionalDouble.of(2.0)
    );

    CorpusRef corpus = uniqueCorpus();
    quantizedStore.ingest(corpus, List.of(
        new ChunkInput("quantized search content", "doc-1", Map.of())
    ));

    List<RetrievedChunk> results = quantizedRetriever.retrieve(
        RetrievalQuery.of("quantized"), corpus, 10, null);

    assertThat(results).isNotEmpty();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest#quantizedRetrieverIngestsAndRetrieves`

Expected: Compilation failure — constructor doesn't accept `DenseQuantization` + `OptionalDouble`.

- [ ] **Step 3: Implement blocking retriever changes**

Modify `HybridCaseRetriever`:

1. Add fields:
   ```java
   private final DenseQuantization quantizationType;
   private final OptionalDouble oversampling;
   ```

2. Add constructor parameters after `TenantGuard tenantGuard`: `DenseQuantization quantizationType, OptionalDouble oversampling`

3. Store fields in constructor body.

4. Add import: `import java.util.OptionalDouble;`

5. Add imports:
   ```java
   import io.qdrant.client.grpc.Points.SearchParams;
   import io.qdrant.client.grpc.Points.QuantizationSearchParams;
   ```

6. Add private helper method:
   ```java
   private SearchParams quantizationSearchParams() {
       return SearchParams.newBuilder()
           .setQuantization(QuantizationSearchParams.newBuilder()
               .setOversampling(oversampling.getAsDouble())
               .setRescore(true)
               .build())
           .build();
   }
   ```

7. In the hybrid path (inside `if (sparseEmbedder != null)`), after building `densePrefetch` and before `mergedFilter.ifPresent(densePrefetch::setFilter)`, add:
   ```java
   if (quantizationType != DenseQuantization.NONE && oversampling.isPresent()) {
       densePrefetch.setParams(quantizationSearchParams());
   }
   ```

8. In the dense-only path (`else` block), after building `builder` and before `mergedFilter.ifPresent(builder::setFilter)`, add:
   ```java
   if (quantizationType != DenseQuantization.NONE && oversampling.isPresent()) {
       builder.setParams(quantizationSearchParams());
   }
   ```

9. Update all existing constructor calls in `HybridCaseRetrieverTest.setUp()` and other test methods to add `DenseQuantization.NONE, OptionalDouble.empty()` as the last two arguments.

- [ ] **Step 4: Run blocking retriever tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest`

Expected: All tests PASS.

- [ ] **Step 5: Implement reactive retriever changes**

Same pattern as blocking. Modify `ReactiveHybridCaseRetriever`:

1. Add `DenseQuantization quantizationType` and `OptionalDouble oversampling` fields + constructor params.
2. Add `quantizationSearchParams()` helper.
3. Apply `SearchParams` to the dense prefetch in `executeQuery()` (hybrid path) and the dense-only `QueryPoints.Builder` (dense-only path).
4. Update all constructor calls in `ReactiveHybridCaseRetrieverTest`.

- [ ] **Step 6: Run reactive retriever tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveHybridCaseRetrieverTest`

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java
```

Message: `feat(#31): retriever search-time oversampling for quantized dense vectors`

---

### Task 5: CDI producer wiring

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java`

**Interfaces:**
- Consumes: `MatryoshkaEmbeddingModel` (Task 1), `DenseQuantization` (Task 2), `RagConfig.MatryoshkaConfig` + `RagConfig.QuantizationConfig` (Task 2), updated ingestor constructors (Task 3), updated retriever constructors (Task 4)
- Produces: Fully wired CDI beans with Matryoshka + quantization support

- [ ] **Step 1: Modify blocking producer**

In `RagBeanProducer`:

1. Add private helper:
   ```java
   private EmbeddingModel effectiveEmbeddingModel() {
       return config.matryoshka().dimension().isPresent()
           ? new MatryoshkaEmbeddingModel(embeddingModel,
               config.matryoshka().dimension().getAsInt())
           : embeddingModel;
   }
   ```

2. In `corpusStore()`, replace `embeddingModel` with `effectiveEmbeddingModel()` and add quantization params:
   ```java
   return new QdrantEmbeddingIngestor(
       client,
       effectiveEmbeddingModel(),
       sparseEmbedder,
       config.tenancyStrategy(),
       config.denseVectorName(),
       config.sparseVectorName(),
       tenantGuard,
       config.embeddingBatchSize(),
       config.quantization().type(),
       config.quantization().alwaysRam());
   ```

3. In `caseRetriever()`, replace `embeddingModel` with `effectiveEmbeddingModel()` and add quantization + oversampling:
   ```java
   return new HybridCaseRetriever(
       client,
       effectiveEmbeddingModel(),
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
       tenantGuard,
       config.quantization().type(),
       config.quantization().oversampling());
   ```

- [ ] **Step 2: Modify reactive producer**

In `ReactiveRagBeanProducer`:

1. Remove the `denseDimension` field and the `@PostConstruct init()` method entirely.

2. Add `effectiveEmbeddingModel()` helper (same as blocking).

3. In `corpusStore()`, replace `embeddingModel` with `effectiveEmbeddingModel()`, remove the `denseDimension` argument, and add quantization params:
   ```java
   return new ReactiveQdrantEmbeddingIngestor(
       client, effectiveEmbeddingModel(), sparseEmbedder,
       config.tenancyStrategy(),
       config.denseVectorName(), config.sparseVectorName(),
       config.quantization().type(),
       config.quantization().alwaysRam(),
       TenantGuard.of(principal),
       config.embeddingBatchSize());
   ```

4. In `caseRetriever()`, replace `embeddingModel` with `effectiveEmbeddingModel()` and add quantization + oversampling:
   ```java
   return new ReactiveHybridCaseRetriever(
       client, effectiveEmbeddingModel(), sparseEmbedder,
       config.tenancyStrategy(),
       config.denseVectorName(), config.sparseVectorName(),
       config.retrieval().denseTopK(), config.retrieval().sparseTopK(),
       config.retrieval().rrfK(), config.retrieval().rerankEnabled(),
       config.retrieval().rerankTopN(), reranker, tenantGuard,
       config.quantization().type(),
       config.quantization().oversampling());
   ```

- [ ] **Step 3: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: All tests PASS. This is the final integration verification — all constructor signatures now match, all config wired.

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java
```

Message: `feat(#31): CDI producer wiring — Matryoshka decorator + quantization config`

- [ ] **Step 5: Run the full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: BUILD SUCCESS across all modules. Modules outside `rag` (inference-*, rag-api, rag-testing, rag-crag, rag-expansion, corpus-*, examples) are unaffected.
