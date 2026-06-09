# Native Reactive Qdrant + Bridge Thread-Offloading Tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the worker-pool-based blocking-to-reactive bridges with native reactive Qdrant implementations using `ListenableFuture` → `Uni` bridging, and add thread-offloading regression tests to the existing bridges.

**Architecture:** `QdrantFutures.toUni()` bridges Guava `ListenableFuture` to Mutiny `Uni` via `emitter()` + `FutureCallback`. Two new plain-POJO classes (`ReactiveQdrantCorpusStore`, `ReactiveHybridCaseRetriever`) implement the reactive SPIs with natively async Qdrant calls. A build-gated `ReactiveRagBeanProducer` (`@IfBuildProperty` + `@Startup`) produces them when `casehub.rag.reactive.enabled=true`. Blocking ONNX embedding is offloaded to the worker pool; Qdrant I/O is natively async.

**Tech Stack:** Java 21, Quarkus 3.32.2, Mutiny 3.1.1, Qdrant Java client 1.18.1 (Guava `ListenableFuture`), LangChain4j 1.14.1, Testcontainers

**Spec:** `specs/2026-06-09-native-reactive-qdrant-design.md` (workspace)

**Project repo:** `/Users/mdproctor/claude/casehub/neural-text`

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

**Build single module:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `rag/src/main/java/io/casehub/rag/runtime/QdrantFutures.java` | Create | `ListenableFuture` → `Uni` bridge with cancellation |
| `rag/src/test/java/io/casehub/rag/runtime/QdrantFuturesTest.java` | Create | Unit test: success, failure, cancellation propagation |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStore.java` | Create | Native reactive `ReactiveCorpusStore` impl |
| `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStoreTest.java` | Create | Testcontainers integration test |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java` | Create | Native reactive `ReactiveCaseRetriever` impl |
| `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java` | Create | Testcontainers integration test |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java` | Create | `@IfBuildProperty` + `@Startup` CDI producer |
| `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java` | Modify | Add thread-offloading assertions for all 4 methods |
| `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java` | Modify | Add thread-offloading assertion for `retrieve` |
| `rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java` | Modify | Add class-level Javadoc |
| `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java` | Modify | Add class-level Javadoc |

---

### Task 1: QdrantFutures — ListenableFuture → Uni bridge

**Files:**
- Create: `rag/src/test/java/io/casehub/rag/runtime/QdrantFuturesTest.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/QdrantFutures.java`

- [ ] **Step 1: Write the failing test — success propagation**

```java
package io.casehub.rag.runtime;

import com.google.common.util.concurrent.SettableFuture;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class QdrantFuturesTest {

    @Test
    void successPropagatesItemToUni() {
        SettableFuture<String> future = SettableFuture.create();
        var uni = QdrantFutures.<String>toUni(future);

        future.set("hello");

        String result = uni.await().indefinitely();
        assertThat(result).isEqualTo("hello");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantFuturesTest#successPropagatesItemToUni -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — `QdrantFutures` does not exist

- [ ] **Step 3: Write minimal QdrantFutures implementation**

```java
package io.casehub.rag.runtime;

import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.MoreExecutors;
import io.smallrye.mutiny.Uni;

final class QdrantFutures {

    private QdrantFutures() {}

    static <T> Uni<T> toUni(ListenableFuture<T> future) {
        return Uni.createFrom().emitter(em -> {
            em.onTermination(() -> future.cancel(false));
            Futures.addCallback(future, new FutureCallback<>() {
                @Override
                public void onSuccess(T result) {
                    em.complete(result);
                }

                @Override
                public void onFailure(Throwable t) {
                    em.fail(t);
                }
            }, MoreExecutors.directExecutor());
        });
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantFuturesTest#successPropagatesItemToUni`
Expected: PASS

- [ ] **Step 5: Write failure and cancellation tests**

Add to `QdrantFuturesTest`:

```java
@Test
void failurePropagatesExceptionToUni() {
    SettableFuture<String> future = SettableFuture.create();
    var uni = QdrantFutures.<String>toUni(future);

    var cause = new RuntimeException("boom");
    future.setException(cause);

    assertThatThrownBy(() -> uni.await().indefinitely())
        .isInstanceOf(RuntimeException.class)
        .hasMessage("boom");
}

@Test
void cancellingUniCancelsListenableFuture() {
    SettableFuture<String> future = SettableFuture.create();
    var uni = QdrantFutures.<String>toUni(future);

    var cancellable = uni.subscribe().with(item -> {}, failure -> {});
    cancellable.cancel();

    assertThat(future.isCancelled()).isTrue();
}

@Test
void alreadyCompletedFutureDeliversImmediately() {
    SettableFuture<Integer> future = SettableFuture.create();
    future.set(42);

    Integer result = QdrantFutures.<Integer>toUni(future).await().indefinitely();
    assertThat(result).isEqualTo(42);
}
```

- [ ] **Step 6: Run all QdrantFutures tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantFuturesTest`
Expected: All 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/QdrantFutures.java rag/src/test/java/io/casehub/rag/runtime/QdrantFuturesTest.java
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#13): QdrantFutures — ListenableFuture to Uni bridge with cancellation propagation"
```

---

### Task 2: ReactiveQdrantCorpusStore — test first, then implement

**Files:**
- Create: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStoreTest.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStore.java`

- [ ] **Step 1: Write the failing test class**

Mirror `QdrantCorpusStoreTest` structure — same Testcontainers setup, same `StubEmbeddingModel`, same `SparseEmbedder` stub. Construct `ReactiveQdrantCorpusStore` directly via constructor. Also construct a blocking `QdrantCorpusStore` for ingest setup in retriever tests later.

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Testcontainers
class ReactiveQdrantCorpusStoreTest {

    @SuppressWarnings("resource")
    @Container
    static final GenericContainer<?> qdrant = new GenericContainer<>("qdrant/qdrant:v1.18.0")
        .withExposedPorts(6334);

    private static final int DENSE_DIM = 4;
    private static final String TENANT = "tenant-1";
    private static final AtomicInteger corpusCounter = new AtomicInteger();

    private QdrantClient client;
    private ReactiveQdrantCorpusStore store;

    @BeforeEach
    void setUp() {
        client = new QdrantClient(
            QdrantGrpcClient.newBuilder(
                qdrant.getHost(),
                qdrant.getMappedPort(6334),
                false
            ).build()
        );

        EmbeddingModel embeddingModel = new StubEmbeddingModel(DENSE_DIM);

        InMemoryInferenceModel spladeModel = InMemoryInferenceModel.returning(
            0.5f, 0.0f, 0.3f, 0.0f, 0.8f, 0.0f, 0.0f, 0.2f
        );
        SparseEmbedder sparseEmbedder = new SparseEmbedder(spladeModel);

        CurrentPrincipal principal = stubPrincipal(TENANT);

        store = new ReactiveQdrantCorpusStore(
            client, embeddingModel, sparseEmbedder,
            TenancyStrategy.SEPARATE_COLLECTIONS,
            "dense", "sparse", DENSE_DIM,
            principal
        );
    }

    @Test
    void ingestCreatesCollectionAndUpserts() throws Exception {
        CorpusRef corpus = uniqueCorpus();
        store.ingest(corpus, List.of(
            new ChunkInput("first chunk", "doc-1", Map.of("key", "val"))
        )).await().indefinitely();

        assertThat(client.collectionExistsAsync(
            TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get())
            .isTrue();
        List<String> docs = store.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactly("doc-1");
    }

    @Test
    void ingestMultipleDocuments() {
        CorpusRef corpus = uniqueCorpus();
        store.ingest(corpus, List.of(
            new ChunkInput("chunk a", "doc-1", Map.of()),
            new ChunkInput("chunk b", "doc-1", Map.of())
        )).await().indefinitely();
        store.ingest(corpus, List.of(
            new ChunkInput("chunk c", "doc-2", Map.of())
        )).await().indefinitely();

        List<String> docs = store.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactlyInAnyOrder("doc-1", "doc-2");
    }

    @Test
    void deleteDocument() {
        CorpusRef corpus = uniqueCorpus();
        store.ingest(corpus, List.of(
            new ChunkInput("chunk a", "doc-1", Map.of()),
            new ChunkInput("chunk b", "doc-2", Map.of())
        )).await().indefinitely();

        store.deleteDocument(corpus, "doc-1").await().indefinitely();

        List<String> docs = store.listDocuments(corpus).await().indefinitely();
        assertThat(docs).containsExactly("doc-2");
    }

    @Test
    void deleteCorpusSeparateMode() throws Exception {
        CorpusRef corpus = uniqueCorpus();
        String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

        store.ingest(corpus, List.of(
            new ChunkInput("content", "doc-1", Map.of())
        )).await().indefinitely();
        assertThat(client.collectionExistsAsync(collection).get()).isTrue();

        store.deleteCorpus(corpus).await().indefinitely();

        assertThat(client.collectionExistsAsync(collection).get()).isFalse();
    }

    @Test
    void tenancyMismatchThrows() {
        CorpusRef wrongTenant = new CorpusRef("other-tenant", "corpus");

        assertThatThrownBy(() -> store.ingest(wrongTenant, List.of(
            new ChunkInput("text", "doc-1", Map.of()))).await().indefinitely())
            .isInstanceOf(SecurityException.class);

        assertThatThrownBy(() -> store.deleteDocument(wrongTenant, "doc-1")
            .await().indefinitely())
            .isInstanceOf(SecurityException.class);

        assertThatThrownBy(() -> store.deleteCorpus(wrongTenant)
            .await().indefinitely())
            .isInstanceOf(SecurityException.class);

        assertThatThrownBy(() -> store.listDocuments(wrongTenant)
            .await().indefinitely())
            .isInstanceOf(SecurityException.class);
    }

    @Test
    void listDocumentsOnNonExistentCorpusReturnsEmpty() {
        CorpusRef corpus = uniqueCorpus();
        List<String> docs = store.listDocuments(corpus).await().indefinitely();
        assertThat(docs).isEmpty();
    }

    // --- helpers ---

    private CorpusRef uniqueCorpus() {
        return new CorpusRef(TENANT, "rxcorpus" + corpusCounter.incrementAndGet());
    }

    private static CurrentPrincipal stubPrincipal(String tenantId) {
        return new CurrentPrincipal() {
            @Override public String actorId() { return "test-actor"; }
            @Override public Set<String> groups() { return Set.of(); }
            @Override public String tenancyId() { return tenantId; }
            @Override public boolean isCrossTenantAdmin() { return false; }
        };
    }

    private static final class StubEmbeddingModel implements EmbeddingModel {
        private final int dim;
        StubEmbeddingModel(int dim) { this.dim = dim; }
        @Override
        public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
            List<Embedding> embeddings = new ArrayList<>(segments.size());
            float[] vec = new float[dim];
            for (int i = 0; i < dim; i++) vec[i] = 0.1f;
            for (int i = 0; i < segments.size(); i++) {
                embeddings.add(Embedding.from(vec));
            }
            return Response.from(embeddings);
        }
        @Override
        public int dimension() { return dim; }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveQdrantCorpusStoreTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — `ReactiveQdrantCorpusStore` does not exist

- [ ] **Step 3: Implement ReactiveQdrantCorpusStore**

Create `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStore.java`:

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.ReactiveCorpusStore;
import io.qdrant.client.ConditionFactory;
import io.qdrant.client.PointIdFactory;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.ValueFactory;
import io.qdrant.client.VectorFactory;
import io.qdrant.client.VectorsFactory;
import io.qdrant.client.WithPayloadSelectorFactory;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.SparseVectorConfig;
import io.qdrant.client.grpc.Collections.SparseVectorParams;
import io.qdrant.client.grpc.Collections.VectorParams;
import io.qdrant.client.grpc.Collections.VectorParamsMap;
import io.qdrant.client.grpc.Collections.VectorsConfig;
import io.qdrant.client.grpc.Common.Filter;
import io.qdrant.client.grpc.Common.PointId;
import io.qdrant.client.grpc.JsonWithInt.Value;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.RetrievedPoint;
import io.qdrant.client.grpc.Points.ScrollPoints;
import io.qdrant.client.grpc.Points.Vector;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public class ReactiveQdrantCorpusStore implements ReactiveCorpusStore {

    private final QdrantClient client;
    private final EmbeddingModel embeddingModel;
    private final SparseEmbedder sparseEmbedder;
    private final TenancyStrategy tenancyStrategy;
    private final String denseVectorName;
    private final String sparseVectorName;
    private final int denseDimension;
    private final CurrentPrincipal currentPrincipal;

    private final ConcurrentHashMap<String, Uni<Void>> ensuredCollections = new ConcurrentHashMap<>();

    public ReactiveQdrantCorpusStore(
            QdrantClient client,
            EmbeddingModel embeddingModel,
            SparseEmbedder sparseEmbedder,
            TenancyStrategy tenancyStrategy,
            String denseVectorName,
            String sparseVectorName,
            int denseDimension,
            CurrentPrincipal currentPrincipal) {
        this.client = client;
        this.embeddingModel = embeddingModel;
        this.sparseEmbedder = sparseEmbedder;
        this.tenancyStrategy = tenancyStrategy;
        this.denseVectorName = denseVectorName;
        this.sparseVectorName = sparseVectorName;
        this.denseDimension = denseDimension;
        this.currentPrincipal = currentPrincipal;
    }

    @Override
    public Uni<Void> ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);

        return ensureCollection(collection)
            .chain(() -> Uni.createFrom().item(() -> {
                List<TextSegment> segments = new ArrayList<>(chunks.size());
                List<String> texts = new ArrayList<>(chunks.size());
                for (ChunkInput chunk : chunks) {
                    segments.add(TextSegment.from(chunk.content()));
                    texts.add(chunk.content());
                }
                Response<List<Embedding>> denseResponse = embeddingModel.embedAll(segments);
                List<Map<Integer, Float>> sparseEmbeddings = sparseEmbedder.embedBatch(texts);
                return new EmbeddingResult(denseResponse.content(), sparseEmbeddings);
            }).runSubscriptionOn(Infrastructure.getDefaultWorkerPool()))
            .chain(embeddings -> {
                List<PointStruct> points = new ArrayList<>(chunks.size());
                for (int i = 0; i < chunks.size(); i++) {
                    points.add(buildPoint(chunks.get(i), corpus,
                        embeddings.dense.get(i), embeddings.sparse.get(i)));
                }
                return QdrantFutures.toUni(client.upsertAsync(collection, points))
                    .replaceWithVoid();
            });
    }

    @Override
    public Uni<Void> deleteDocument(CorpusRef corpus, String sourceDocumentId) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);

        Filter.Builder filterBuilder = Filter.newBuilder()
            .addMust(ConditionFactory.matchKeyword("sourceDocumentId", sourceDocumentId));
        tenancyStrategy.tenantFilter(corpus)
            .ifPresent(tf -> tf.getMustList().forEach(filterBuilder::addMust));

        return QdrantFutures.toUni(client.deleteAsync(collection, filterBuilder.build()))
            .replaceWithVoid();
    }

    @Override
    public Uni<Void> deleteCorpus(CorpusRef corpus) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);

        if (tenancyStrategy == TenancyStrategy.SEPARATE_COLLECTIONS) {
            return QdrantFutures.toUni(client.deleteCollectionAsync(collection))
                .invoke(() -> ensuredCollections.remove(collection))
                .replaceWithVoid();
        } else {
            Optional<Filter> tenantFilter = tenancyStrategy.tenantFilter(corpus);
            if (tenantFilter.isPresent()) {
                return QdrantFutures.toUni(client.deleteAsync(collection, tenantFilter.get()))
                    .replaceWithVoid();
            }
            return Uni.createFrom().voidItem();
        }
    }

    @Override
    public Uni<List<String>> listDocuments(CorpusRef corpus) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);
        Optional<Filter> tenantFilter = tenancyStrategy.tenantFilter(corpus);

        return QdrantFutures.<Boolean>toUni(client.collectionExistsAsync(collection))
            .chain(exists -> {
                if (!exists) {
                    return Uni.createFrom().item(List.<String>of());
                }
                return scrollPage(collection, tenantFilter, null, new LinkedHashSet<>())
                    .map(List::copyOf);
            });
    }

    private Uni<Void> ensureCollection(String collection) {
        return ensuredCollections.computeIfAbsent(collection, k ->
            QdrantFutures.<Boolean>toUni(client.collectionExistsAsync(k))
                .chain(exists -> {
                    if (exists) return Uni.createFrom().voidItem();
                    return QdrantFutures.toUni(
                        client.createCollectionAsync(buildCreateRequest(k)))
                        .replaceWithVoid();
                })
                .onFailure().invoke(() -> ensuredCollections.remove(k))
                .memoize().indefinitely()
        );
    }

    private Uni<Set<String>> scrollPage(String collection, Optional<Filter> tenantFilter,
            PointId offset, Set<String> accumulator) {
        ScrollPoints.Builder builder = ScrollPoints.newBuilder()
            .setCollectionName(collection)
            .setLimit(100)
            .setWithPayload(WithPayloadSelectorFactory.enable(true));
        tenantFilter.ifPresent(builder::setFilter);
        if (offset != null) {
            builder.setOffset(offset);
        }

        return QdrantFutures.toUni(client.scrollAsync(builder.build()))
            .flatMap(response -> {
                for (RetrievedPoint point : response.getResultList()) {
                    Value docId = point.getPayloadMap().get("sourceDocumentId");
                    if (docId != null && docId.hasStringValue()) {
                        accumulator.add(docId.getStringValue());
                    }
                }
                if (!response.hasNextPageOffset()) {
                    return Uni.createFrom().item(accumulator);
                }
                return scrollPage(collection, tenantFilter,
                    response.getNextPageOffset(), accumulator);
            });
    }

    private CreateCollection buildCreateRequest(String collection) {
        VectorParams denseParams = VectorParams.newBuilder()
            .setSize(denseDimension)
            .setDistance(Distance.Cosine)
            .build();
        VectorParamsMap paramsMap = VectorParamsMap.newBuilder()
            .putMap(denseVectorName, denseParams)
            .build();
        SparseVectorConfig sparseConfig = SparseVectorConfig.newBuilder()
            .putMap(sparseVectorName, SparseVectorParams.getDefaultInstance())
            .build();
        return CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(VectorsConfig.newBuilder().setParamsMap(paramsMap).build())
            .setSparseVectorsConfig(sparseConfig)
            .build();
    }

    private PointStruct buildPoint(ChunkInput chunk, CorpusRef corpus,
            Embedding denseEmbedding, Map<Integer, Float> sparseMap) {
        Vector denseVector = VectorFactory.vector(denseEmbedding.vectorAsList());
        List<Float> sparseValues = new ArrayList<>(sparseMap.size());
        List<Integer> sparseIndices = new ArrayList<>(sparseMap.size());
        for (Map.Entry<Integer, Float> entry : sparseMap.entrySet()) {
            sparseIndices.add(entry.getKey());
            sparseValues.add(entry.getValue());
        }
        Vector sparseVector = VectorFactory.vector(sparseValues, sparseIndices);
        Map<String, Vector> namedVectors = Map.of(
            denseVectorName, denseVector,
            sparseVectorName, sparseVector
        );
        Map<String, Value> payload = new HashMap<>();
        payload.put("content", ValueFactory.value(chunk.content()));
        payload.put("sourceDocumentId", ValueFactory.value(chunk.sourceDocumentId()));
        payload.put("tenantId", ValueFactory.value(corpus.tenantId()));
        for (Map.Entry<String, String> meta : chunk.metadata().entrySet()) {
            payload.put(meta.getKey(), ValueFactory.value(meta.getValue()));
        }
        return PointStruct.newBuilder()
            .setId(PointIdFactory.id(UUID.randomUUID()))
            .setVectors(VectorsFactory.namedVectors(namedVectors))
            .putAllPayload(payload)
            .build();
    }

    private record EmbeddingResult(List<Embedding> dense, List<Map<Integer, Float>> sparse) {}
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveQdrantCorpusStoreTest`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStore.java rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStoreTest.java
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#13): ReactiveQdrantCorpusStore — native reactive CorpusStore with ensureCollection memoization"
```

---

### Task 3: ReactiveHybridCaseRetriever — test first, then implement

**Files:**
- Create: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`

- [ ] **Step 1: Write the failing test class**

Uses a blocking `QdrantCorpusStore` for ingest (creating collections + data), then retrieves via the reactive retriever. Mirrors `HybridCaseRetrieverTest`.

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Testcontainers
class ReactiveHybridCaseRetrieverTest {

    @SuppressWarnings("resource")
    @Container
    static final GenericContainer<?> qdrant = new GenericContainer<>("qdrant/qdrant:v1.18.0")
        .withExposedPorts(6334);

    private static final int DENSE_DIM = 4;
    private static final String TENANT = "tenant-1";
    private static final String DENSE_VECTOR_NAME = "dense";
    private static final String SPARSE_VECTOR_NAME = "sparse";
    private static final AtomicInteger corpusCounter = new AtomicInteger();

    private QdrantClient client;
    private QdrantCorpusStore store; // blocking, for test data setup
    private ReactiveHybridCaseRetriever retriever;

    @BeforeEach
    void setUp() {
        client = new QdrantClient(
            QdrantGrpcClient.newBuilder(
                qdrant.getHost(),
                qdrant.getMappedPort(6334),
                false
            ).build()
        );

        EmbeddingModel embeddingModel = new StubEmbeddingModel(DENSE_DIM);

        InMemoryInferenceModel spladeModel = InMemoryInferenceModel.returning(
            0.5f, 0.0f, 0.3f, 0.0f, 0.8f, 0.0f, 0.0f, 0.2f
        );
        SparseEmbedder sparseEmbedder = new SparseEmbedder(spladeModel);

        CurrentPrincipal principal = stubPrincipal(TENANT);

        store = new QdrantCorpusStore(
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
    }

    @Test
    void retrieveFromIngestedCorpus() {
        CorpusRef corpus = uniqueCorpus();
        store.ingest(corpus, List.of(
            new ChunkInput("The quick brown fox jumps over the lazy dog", "doc-1",
                Map.of("category", "animals")),
            new ChunkInput("Machine learning is a subset of artificial intelligence", "doc-2",
                Map.of("category", "tech"))
        ));

        List<RetrievedChunk> results = retriever.retrieve("brown fox", corpus, 10)
            .await().indefinitely();

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(chunk -> {
            assertThat(chunk.content()).isNotBlank();
            assertThat(chunk.sourceDocumentId()).isNotBlank();
            assertThat(chunk.relevanceScore()).isGreaterThan(0.0);
        });
        assertThat(results).anyMatch(chunk ->
            "animals".equals(chunk.metadata().get("category"))
            || "tech".equals(chunk.metadata().get("category")));
    }

    @Test
    void retrieveRespectsMaxResults() {
        CorpusRef corpus = uniqueCorpus();
        store.ingest(corpus, List.of(
            new ChunkInput("chunk one about cats", "doc-1", Map.of()),
            new ChunkInput("chunk two about dogs", "doc-2", Map.of()),
            new ChunkInput("chunk three about birds", "doc-3", Map.of())
        ));

        List<RetrievedChunk> results = retriever.retrieve("animals", corpus, 1)
            .await().indefinitely();

        assertThat(results).hasSizeLessThanOrEqualTo(1);
    }

    @Test
    void retrieveEmptyCorpus() {
        CorpusRef corpus = uniqueCorpus();

        List<RetrievedChunk> results = retriever.retrieve("anything", corpus, 10)
            .await().indefinitely();

        assertThat(results).isEmpty();
    }

    @Test
    void tenancyMismatchThrows() {
        CorpusRef wrongTenant = new CorpusRef("other-tenant", "corpus");

        assertThatThrownBy(() -> retriever.retrieve("query", wrongTenant, 10)
            .await().indefinitely())
            .isInstanceOf(SecurityException.class);
    }

    // --- helpers ---

    private CorpusRef uniqueCorpus() {
        return new CorpusRef(TENANT, "rxretriever" + corpusCounter.incrementAndGet());
    }

    private static CurrentPrincipal stubPrincipal(String tenantId) {
        return new CurrentPrincipal() {
            @Override public String actorId() { return "test-actor"; }
            @Override public Set<String> groups() { return Set.of(); }
            @Override public String tenancyId() { return tenantId; }
            @Override public boolean isCrossTenantAdmin() { return false; }
        };
    }

    private static final class StubEmbeddingModel implements EmbeddingModel {
        private final int dim;
        StubEmbeddingModel(int dim) { this.dim = dim; }
        @Override
        public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
            List<Embedding> embeddings = new ArrayList<>(segments.size());
            float[] vec = new float[dim];
            for (int i = 0; i < dim; i++) vec[i] = 0.1f;
            for (int i = 0; i < segments.size(); i++) {
                embeddings.add(Embedding.from(vec));
            }
            return Response.from(embeddings);
        }
        @Override
        public int dimension() { return dim; }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveHybridCaseRetrieverTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — `ReactiveHybridCaseRetriever` does not exist

- [ ] **Step 3: Implement ReactiveHybridCaseRetriever**

Create `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`:

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.inference.tasks.RankedResult;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RetrievedChunk;
import io.qdrant.client.QueryFactory;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.WithPayloadSelectorFactory;
import io.qdrant.client.grpc.Common.Filter;
import io.qdrant.client.grpc.JsonWithInt.Value;
import io.qdrant.client.grpc.Points.PrefetchQuery;
import io.qdrant.client.grpc.Points.QueryPoints;
import io.qdrant.client.grpc.Points.Rrf;
import io.qdrant.client.grpc.Points.ScoredPoint;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public class ReactiveHybridCaseRetriever implements ReactiveCaseRetriever {

    private static final java.util.Set<String> RESERVED_PAYLOAD_KEYS =
        java.util.Set.of("content", "sourceDocumentId", "tenantId");

    private final QdrantClient client;
    private final EmbeddingModel embeddingModel;
    private final SparseEmbedder sparseEmbedder;
    private final TenancyStrategy tenancyStrategy;
    private final String denseVectorName;
    private final String sparseVectorName;
    private final int denseTopK;
    private final int sparseTopK;
    private final int rrfK;
    private final boolean rerankEnabled;
    private final int rerankTopN;
    private final CrossEncoderReranker reranker;
    private final CurrentPrincipal currentPrincipal;

    public ReactiveHybridCaseRetriever(
            QdrantClient client,
            EmbeddingModel embeddingModel,
            SparseEmbedder sparseEmbedder,
            TenancyStrategy tenancyStrategy,
            String denseVectorName,
            String sparseVectorName,
            int denseTopK,
            int sparseTopK,
            int rrfK,
            boolean rerankEnabled,
            int rerankTopN,
            CrossEncoderReranker reranker,
            CurrentPrincipal currentPrincipal) {
        this.client = client;
        this.embeddingModel = embeddingModel;
        this.sparseEmbedder = sparseEmbedder;
        this.tenancyStrategy = tenancyStrategy;
        this.denseVectorName = denseVectorName;
        this.sparseVectorName = sparseVectorName;
        this.denseTopK = denseTopK;
        this.sparseTopK = sparseTopK;
        this.rrfK = rrfK;
        this.rerankEnabled = rerankEnabled;
        this.rerankTopN = rerankTopN;
        this.reranker = reranker;
        this.currentPrincipal = currentPrincipal;
    }

    @Override
    public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);

        String collection = tenancyStrategy.collectionName(corpus);
        Optional<Filter> tenantFilter = tenancyStrategy.tenantFilter(corpus);

        return QdrantFutures.<Boolean>toUni(client.collectionExistsAsync(collection))
            .chain(exists -> {
                if (!exists) {
                    return Uni.createFrom().item(List.<RetrievedChunk>of());
                }
                return Uni.createFrom().item(() -> embedQuery(query))
                    .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
                    .chain(embeddings -> executeQuery(collection, tenantFilter,
                        embeddings, maxResults))
                    .map(scoredPoints -> mapToChunks(scoredPoints))
                    .chain(chunks -> maybeRerank(query, chunks, maxResults));
            });
    }

    private QueryEmbeddings embedQuery(String query) {
        Embedding denseEmbedding = embeddingModel.embed(TextSegment.from(query)).content();
        Map<Integer, Float> sparseMap = sparseEmbedder.embed(query);
        return new QueryEmbeddings(denseEmbedding, sparseMap);
    }

    private Uni<List<ScoredPoint>> executeQuery(String collection,
            Optional<Filter> tenantFilter, QueryEmbeddings embeddings, int maxResults) {
        List<Float> sparseValues = new ArrayList<>(embeddings.sparse.size());
        List<Integer> sparseIndices = new ArrayList<>(embeddings.sparse.size());
        for (Map.Entry<Integer, Float> entry : embeddings.sparse.entrySet()) {
            sparseIndices.add(entry.getKey());
            sparseValues.add(entry.getValue());
        }

        PrefetchQuery.Builder densePrefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(embeddings.dense.vectorAsList()))
            .setUsing(denseVectorName)
            .setLimit(denseTopK);
        tenantFilter.ifPresent(densePrefetch::setFilter);

        PrefetchQuery.Builder sparsePrefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(sparseValues, sparseIndices))
            .setUsing(sparseVectorName)
            .setLimit(sparseTopK);
        tenantFilter.ifPresent(sparsePrefetch::setFilter);

        int queryLimit = rerankEnabled && reranker != null
            ? Math.max(maxResults, rerankTopN)
            : maxResults;

        QueryPoints queryPoints = QueryPoints.newBuilder()
            .setCollectionName(collection)
            .addPrefetch(densePrefetch)
            .addPrefetch(sparsePrefetch)
            .setQuery(QueryFactory.rrf(Rrf.newBuilder().setK(rrfK).build()))
            .setLimit(queryLimit)
            .setWithPayload(WithPayloadSelectorFactory.enable(true))
            .build();

        return QdrantFutures.toUni(client.queryAsync(queryPoints));
    }

    private List<RetrievedChunk> mapToChunks(List<ScoredPoint> scoredPoints) {
        List<RetrievedChunk> chunks = new ArrayList<>(scoredPoints.size());
        for (ScoredPoint point : scoredPoints) {
            Map<String, Value> payload = point.getPayloadMap();
            String content = extractString(payload, "content");
            String sourceDocumentId = extractString(payload, "sourceDocumentId");
            if (content == null || sourceDocumentId == null) continue;

            Map<String, String> metadata = new HashMap<>();
            for (Map.Entry<String, Value> entry : payload.entrySet()) {
                if (!RESERVED_PAYLOAD_KEYS.contains(entry.getKey())
                        && entry.getValue().hasStringValue()) {
                    metadata.put(entry.getKey(), entry.getValue().getStringValue());
                }
            }
            chunks.add(new RetrievedChunk(content, sourceDocumentId,
                point.getScore(), Map.copyOf(metadata)));
        }
        return chunks;
    }

    private Uni<List<RetrievedChunk>> maybeRerank(String query,
            List<RetrievedChunk> chunks, int maxResults) {
        if (!rerankEnabled || reranker == null || chunks.isEmpty()) {
            chunks.sort((a, b) -> Double.compare(b.relevanceScore(), a.relevanceScore()));
            return Uni.createFrom().item(Collections.unmodifiableList(chunks));
        }
        return Uni.createFrom().item(() -> {
            List<String> texts = new ArrayList<>(chunks.size());
            for (RetrievedChunk chunk : chunks) texts.add(chunk.content());
            List<RankedResult> ranked = reranker.rerank(query, texts);
            List<RetrievedChunk> reranked = new ArrayList<>(
                Math.min(ranked.size(), maxResults));
            for (int i = 0; i < Math.min(ranked.size(), maxResults); i++) {
                RankedResult r = ranked.get(i);
                RetrievedChunk original = chunks.get(r.originalIndex());
                reranked.add(new RetrievedChunk(
                    original.content(), original.sourceDocumentId(),
                    r.score(), original.metadata()));
            }
            return Collections.unmodifiableList(reranked);
        }).runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    private static String extractString(Map<String, Value> payload, String key) {
        Value value = payload.get(key);
        if (value != null && value.hasStringValue()) return value.getStringValue();
        return null;
    }

    private record QueryEmbeddings(Embedding dense, Map<Integer, Float> sparse) {}
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveHybridCaseRetrieverTest`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#13): ReactiveHybridCaseRetriever — native reactive hybrid search with RRF fusion"
```

---

### Task 4: ReactiveRagBeanProducer — CDI wiring

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java`

- [ ] **Step 1: Create ReactiveRagBeanProducer**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.model.embedding.EmbeddingModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.quarkus.arc.properties.IfBuildProperty;
import io.quarkus.runtime.Startup;
import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Inject;

@IfBuildProperty(name = "casehub.rag.reactive.enabled", stringValue = "true")
@ApplicationScoped
@Startup
public class ReactiveRagBeanProducer {

    @Inject RagConfig config;
    @Inject io.qdrant.client.QdrantClient client;
    @Inject EmbeddingModel embeddingModel;
    @Inject SparseEmbedder sparseEmbedder;
    @Inject Instance<CrossEncoderReranker> rerankerInstance;
    @Inject CurrentPrincipal currentPrincipal;

    private int denseDimension;

    @PostConstruct
    void init() {
        denseDimension = embeddingModel.dimension();
    }

    @Produces
    @ApplicationScoped
    ReactiveQdrantCorpusStore corpusStore() {
        return new ReactiveQdrantCorpusStore(
            client, embeddingModel, sparseEmbedder,
            config.tenancyStrategy(),
            config.denseVectorName(), config.sparseVectorName(),
            denseDimension, currentPrincipal);
    }

    @Produces
    @ApplicationScoped
    ReactiveHybridCaseRetriever caseRetriever() {
        CrossEncoderReranker reranker = rerankerInstance.isResolvable()
            ? rerankerInstance.get() : null;
        return new ReactiveHybridCaseRetriever(
            client, embeddingModel, sparseEmbedder,
            config.tenancyStrategy(),
            config.denseVectorName(), config.sparseVectorName(),
            config.retrieval().denseTopK(), config.retrieval().sparseTopK(),
            config.retrieval().rrfK(), config.retrieval().rerankEnabled(),
            config.retrieval().rerankTopN(), reranker, currentPrincipal);
    }
}
```

- [ ] **Step 2: Build the rag module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag`
Expected: BUILD SUCCESS — the producer compiles against the impls

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#13): ReactiveRagBeanProducer — @IfBuildProperty + @Startup CDI producer"
```

---

### Task 5: Bridge thread-offloading tests (#14)

**Files:**
- Modify: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`

- [ ] **Step 1: Add thread-offloading tests to BlockingToReactiveCorpusStoreTest**

Add to the existing test class. One test per method (4 methods: ingest, deleteDocument, deleteCorpus, listDocuments). Uses `AtomicLong` thread ID pattern matching platform `BlockingToReactiveBridgeThreadingTest`.

Add the following import and tests to the existing class:

```java
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
```

```java
@Test
void ingest_executesOnWorkerThread() {
    var capturedId = new AtomicLong(Thread.currentThread().getId());
    CorpusStore spy = new CorpusStore() {
        @Override public void ingest(CorpusRef c, List<ChunkInput> ch) {
            capturedId.set(Thread.currentThread().getId());
        }
        @Override public void deleteDocument(CorpusRef c, String id) {}
        @Override public void deleteCorpus(CorpusRef c) {}
        @Override public List<String> listDocuments(CorpusRef c) { return List.of(); }
    };
    var b = new BlockingToReactiveCorpusStore(spy);
    b.ingest(new CorpusRef("t", "c"), List.of(new ChunkInput("x", "d", Map.of())))
        .await().indefinitely();
    assertNotEquals(Thread.currentThread().getId(), capturedId.get(),
        "ingest() must offload to a worker thread");
}

@Test
void deleteDocument_executesOnWorkerThread() {
    var capturedId = new AtomicLong(Thread.currentThread().getId());
    CorpusStore spy = new CorpusStore() {
        @Override public void ingest(CorpusRef c, List<ChunkInput> ch) {}
        @Override public void deleteDocument(CorpusRef c, String id) {
            capturedId.set(Thread.currentThread().getId());
        }
        @Override public void deleteCorpus(CorpusRef c) {}
        @Override public List<String> listDocuments(CorpusRef c) { return List.of(); }
    };
    var b = new BlockingToReactiveCorpusStore(spy);
    b.deleteDocument(new CorpusRef("t", "c"), "d1").await().indefinitely();
    assertNotEquals(Thread.currentThread().getId(), capturedId.get(),
        "deleteDocument() must offload to a worker thread");
}

@Test
void deleteCorpus_executesOnWorkerThread() {
    var capturedId = new AtomicLong(Thread.currentThread().getId());
    CorpusStore spy = new CorpusStore() {
        @Override public void ingest(CorpusRef c, List<ChunkInput> ch) {}
        @Override public void deleteDocument(CorpusRef c, String id) {}
        @Override public void deleteCorpus(CorpusRef c) {
            capturedId.set(Thread.currentThread().getId());
        }
        @Override public List<String> listDocuments(CorpusRef c) { return List.of(); }
    };
    var b = new BlockingToReactiveCorpusStore(spy);
    b.deleteCorpus(new CorpusRef("t", "c")).await().indefinitely();
    assertNotEquals(Thread.currentThread().getId(), capturedId.get(),
        "deleteCorpus() must offload to a worker thread");
}

@Test
void listDocuments_executesOnWorkerThread() {
    var capturedId = new AtomicLong(Thread.currentThread().getId());
    CorpusStore spy = new CorpusStore() {
        @Override public void ingest(CorpusRef c, List<ChunkInput> ch) {}
        @Override public void deleteDocument(CorpusRef c, String id) {}
        @Override public void deleteCorpus(CorpusRef c) {}
        @Override public List<String> listDocuments(CorpusRef c) {
            capturedId.set(Thread.currentThread().getId());
            return List.of();
        }
    };
    var b = new BlockingToReactiveCorpusStore(spy);
    b.listDocuments(new CorpusRef("t", "c")).await().indefinitely();
    assertNotEquals(Thread.currentThread().getId(), capturedId.get(),
        "listDocuments() must offload to a worker thread");
}
```

- [ ] **Step 2: Add thread-offloading test to BlockingToReactiveCaseRetrieverTest**

Add import and test:

```java
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
```

```java
@Test
void retrieve_executesOnWorkerThread() {
    var capturedId = new AtomicLong(Thread.currentThread().getId());
    CaseRetriever spy = (query, corpus, maxResults) -> {
        capturedId.set(Thread.currentThread().getId());
        return List.of();
    };
    var b = new BlockingToReactiveCaseRetriever(spy);
    b.retrieve("q", new CorpusRef("t", "c"), 5).await().indefinitely();
    assertNotEquals(Thread.currentThread().getId(), capturedId.get(),
        "retrieve() must offload to a worker thread");
}
```

- [ ] **Step 3: Run bridge tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="BlockingToReactiveCorpusStoreTest,BlockingToReactiveCaseRetrieverTest"`
Expected: All tests PASS (existing delegation tests + new thread-offloading tests)

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "test(#14): bridge thread-offloading regression tests — all methods verified"
```

---

### Task 6: Javadoc on reactive SPIs

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java`
- Modify: `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java`

- [ ] **Step 1: Add Javadoc to ReactiveCorpusStore**

Add class-level Javadoc before the interface declaration:

```java
/** Non-blocking counterpart of {@link CorpusStore}. Safe to subscribe to from the Vert.x event loop. */
public interface ReactiveCorpusStore {
```

- [ ] **Step 2: Add Javadoc to ReactiveCaseRetriever**

Add class-level Javadoc before the interface declaration:

```java
/** Non-blocking counterpart of {@link CaseRetriever}. Safe to subscribe to from the Vert.x event loop. */
public interface ReactiveCaseRetriever {
```

- [ ] **Step 3: Build rag-api to verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag-api`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "docs(#14): Javadoc on reactive SPIs — non-blocking contract, no delivery thread guarantee"
```

---

### Task 7: Full build verification

- [ ] **Step 1: Run full build with all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile, all tests pass

- [ ] **Step 2: Verify no test regressions**

Check that existing tests are unchanged:
- `QdrantCorpusStoreTest` — PASS (unchanged)
- `HybridCaseRetrieverTest` — PASS (unchanged)
- `BlockingReactiveParityTest` — PASS (unchanged, no new SPI methods)
- `InMemoryReactiveCorpusStoreTest` — PASS (unchanged)
- `InMemoryReactiveCaseRetrieverTest` — PASS (unchanged)

- [ ] **Step 3: Commit if any formatting or import adjustments were needed**

Only if the build required fixes — otherwise skip.
