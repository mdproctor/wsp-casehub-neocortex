# Qdrant Payload Indexes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full-text and keyword payload indexes to Qdrant collections during `ensureCollection()`, with lazy migration for existing collections.

**Architecture:** Extend `ensureCollection()` in both blocking and reactive ingestors with an `ensurePayloadIndexes` helper that creates missing payload indexes (text on `content`, keyword on `sourceDocumentId` and `tenantId`). For existing collections, `payload_schema` from the already-fetched `CollectionInfo` is checked for missing or mistyped indexes. No new classes, no SPI/config changes.

**Tech Stack:** Java 21, Qdrant Java client 1.18.1 (gRPC), Testcontainers, Mutiny (reactive path)

## Global Constraints

- Build with: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Test module: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag`
- Use `mvn` not `./mvnw`
- All changes scoped to `rag/src/main/java/io/casehub/rag/runtime/` and `rag/src/test/java/io/casehub/rag/runtime/`
- No SPI, config, CDI wiring, or retriever changes
- TextIndexParams: `Word` tokenizer, `lowercase=true`, `min_token_len=2`, `max_token_len=40`
- Type mismatch on existing index → `IllegalStateException`
- `wait=true` on all `createPayloadIndexAsync` calls
- Use IntelliJ MCP for all code navigation — never bash grep/find for classes

---

### Task 1: Blocking ingestor — payload indexes + tests

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`

**Interfaces:**
- Consumes: `QdrantClient.createPayloadIndexAsync()`, `CollectionInfo.getPayloadSchemaMap()`, `PayloadSchemaInfo.getDataType()`, `PayloadSchemaType`, `TextIndexParams`, `TokenizerType`, `PayloadIndexParams`
- Produces: `QdrantEmbeddingIngestor.ensurePayloadIndexes(String, Map<String, PayloadSchemaInfo>)` — private, no external consumers

- [ ] **Step 1: Write test — new collection gets all payload indexes**

Add to `QdrantEmbeddingIngestorTest.java`:

```java
@Test
void ensureCollectionCreatesPayloadIndexes() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    var info = client.getCollectionInfoAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get();
    var schema = info.getPayloadSchemaMap();

    assertThat(schema).containsKey("content");
    assertThat(schema.get("content").getDataType())
        .isEqualTo(io.qdrant.client.grpc.Collections.PayloadSchemaType.Text);

    assertThat(schema).containsKey("sourceDocumentId");
    assertThat(schema.get("sourceDocumentId").getDataType())
        .isEqualTo(io.qdrant.client.grpc.Collections.PayloadSchemaType.Keyword);

    assertThat(schema).containsKey("tenantId");
    assertThat(schema.get("tenantId").getDataType())
        .isEqualTo(io.qdrant.client.grpc.Collections.PayloadSchemaType.Keyword);
}
```

Add import: `import io.qdrant.client.grpc.Collections.PayloadSchemaType;` — then replace the three `io.qdrant.client.grpc.Collections.PayloadSchemaType` references with `PayloadSchemaType`.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest#ensureCollectionCreatesPayloadIndexes`

Expected: FAIL — `payload_schema` is empty (no indexes created yet).

- [ ] **Step 3: Write test — migration adds missing indexes to existing collection**

Add to `QdrantEmbeddingIngestorTest.java`:

```java
@Test
void ensureCollectionAddsIndexesToExistingCollection() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

    // Create collection manually — vectors only, no payload indexes
    var denseParams = io.qdrant.client.grpc.Collections.VectorParams.newBuilder()
        .setSize(DENSE_DIM)
        .setDistance(io.qdrant.client.grpc.Collections.Distance.Cosine)
        .build();
    var paramsMap = io.qdrant.client.grpc.Collections.VectorParamsMap.newBuilder()
        .putMap("dense", denseParams)
        .build();
    client.createCollectionAsync(
        io.qdrant.client.grpc.Collections.CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(io.qdrant.client.grpc.Collections.VectorsConfig.newBuilder()
                .setParamsMap(paramsMap).build())
            .build()).get();

    // Ingest triggers ensureCollection on existing collection
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    var info = client.getCollectionInfoAsync(collection).get();
    var schema = info.getPayloadSchemaMap();

    assertThat(schema).containsKey("content");
    assertThat(schema.get("content").getDataType()).isEqualTo(PayloadSchemaType.Text);
    assertThat(schema).containsKey("sourceDocumentId");
    assertThat(schema.get("sourceDocumentId").getDataType()).isEqualTo(PayloadSchemaType.Keyword);
    assertThat(schema).containsKey("tenantId");
    assertThat(schema.get("tenantId").getDataType()).isEqualTo(PayloadSchemaType.Keyword);
}
```

- [ ] **Step 4: Write test — idempotent on already-indexed collection**

Add to `QdrantEmbeddingIngestorTest.java`:

```java
@Test
void ensureCollectionIdempotentOnAlreadyIndexedCollection() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

    // First ingest creates collection + indexes
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    ));

    // Fresh ingestor — knownCollections cache is empty, forces re-check
    QdrantEmbeddingIngestor freshStore = new QdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        Integer.MAX_VALUE,
        DenseQuantization.NONE, true
    );

    // Second ingest on existing collection with indexes already present
    freshStore.ingest(corpus, List.of(
        new ChunkInput("more content", "doc-2", Map.of())
    ));

    assertThat(freshStore.listDocuments(corpus))
        .containsExactlyInAnyOrder("doc-1", "doc-2");
}
```

- [ ] **Step 5: Write test — type mismatch throws IllegalStateException**

Add to `QdrantEmbeddingIngestorTest.java`:

```java
@Test
void ensureCollectionThrowsOnIndexTypeMismatch() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

    // Create collection manually
    var denseParams = io.qdrant.client.grpc.Collections.VectorParams.newBuilder()
        .setSize(DENSE_DIM)
        .setDistance(io.qdrant.client.grpc.Collections.Distance.Cosine)
        .build();
    var paramsMap = io.qdrant.client.grpc.Collections.VectorParamsMap.newBuilder()
        .putMap("dense", denseParams)
        .build();
    client.createCollectionAsync(
        io.qdrant.client.grpc.Collections.CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(io.qdrant.client.grpc.Collections.VectorsConfig.newBuilder()
                .setParamsMap(paramsMap).build())
            .build()).get();

    // Create a Keyword index on 'content' — wrong type (should be Text)
    client.createPayloadIndexAsync(collection, "content",
        PayloadSchemaType.Keyword, null, true, null, null).get();

    // Ingest should detect type mismatch and throw
    assertThatThrownBy(() -> store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of()))))
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("content")
        .hasMessageContaining("Text")
        .hasMessageContaining("Keyword");
}
```

- [ ] **Step 6: Run all four new tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="QdrantEmbeddingIngestorTest#ensureCollectionCreatesPayloadIndexes+ensureCollectionAddsIndexesToExistingCollection+ensureCollectionIdempotentOnAlreadyIndexedCollection+ensureCollectionThrowsOnIndexTypeMismatch"`

Expected: FAIL — `ensurePayloadIndexes` does not exist yet.

- [ ] **Step 7: Implement `ensurePayloadIndexes` in `QdrantEmbeddingIngestor`**

Add imports to `QdrantEmbeddingIngestor.java`:

```java
import io.qdrant.client.grpc.Collections.PayloadIndexParams;
import io.qdrant.client.grpc.Collections.PayloadSchemaInfo;
import io.qdrant.client.grpc.Collections.PayloadSchemaType;
import io.qdrant.client.grpc.Collections.TextIndexParams;
import io.qdrant.client.grpc.Collections.TokenizerType;
```

Add private method after `ensureCollection`:

```java
private void ensurePayloadIndexes(String collection,
        Map<String, PayloadSchemaInfo> existingSchema)
        throws InterruptedException, ExecutionException {
    checkIndexType(existingSchema, "content", PayloadSchemaType.Text, collection);
    checkIndexType(existingSchema, "sourceDocumentId", PayloadSchemaType.Keyword, collection);
    checkIndexType(existingSchema, "tenantId", PayloadSchemaType.Keyword, collection);

    if (!existingSchema.containsKey("content")) {
        PayloadIndexParams textParams = PayloadIndexParams.newBuilder()
            .setTextIndexParams(TextIndexParams.newBuilder()
                .setTokenizer(TokenizerType.Word)
                .setLowercase(true)
                .setMinTokenLen(2)
                .setMaxTokenLen(40)
                .build())
            .build();
        client.createPayloadIndexAsync(collection, "content",
            PayloadSchemaType.Text, textParams, true, null, null).get();
    }
    if (!existingSchema.containsKey("sourceDocumentId")) {
        client.createPayloadIndexAsync(collection, "sourceDocumentId",
            PayloadSchemaType.Keyword, null, true, null, null).get();
    }
    if (!existingSchema.containsKey("tenantId")) {
        client.createPayloadIndexAsync(collection, "tenantId",
            PayloadSchemaType.Keyword, null, true, null, null).get();
    }
}

private static void checkIndexType(Map<String, PayloadSchemaInfo> schema,
        String field, PayloadSchemaType expected, String collection) {
    PayloadSchemaInfo info = schema.get(field);
    if (info != null && info.getDataType() != expected) {
        throw new IllegalStateException(
            "Payload index type mismatch on field '" + field
                + "' in collection '" + collection
                + "': expected " + expected + " but found " + info.getDataType());
    }
}
```

- [ ] **Step 8: Wire `ensurePayloadIndexes` into `ensureCollection`**

In the `ensureCollection` method, modify the existing-collection path. Replace:

```java
                knownCollections.add(collection);
                return;
            }
```

(the block after dimension validation) with:

```java
                ensurePayloadIndexes(collection, info.getPayloadSchemaMap());
                knownCollections.add(collection);
                return;
            }
```

In the new-collection path, after `client.createCollectionAsync(createRequest).get();` and before `knownCollections.add(collection);`, add:

```java
            ensurePayloadIndexes(collection, Map.of());
```

- [ ] **Step 9: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantEmbeddingIngestorTest`

Expected: ALL PASS (existing tests + 4 new tests).

- [ ] **Step 10: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java
git commit -m "feat(#47,#50): payload indexes in blocking QdrantEmbeddingIngestor

Add ensurePayloadIndexes() to ensureCollection() — creates full-text index
on content (Word tokenizer) and keyword indexes on sourceDocumentId and
tenantId. Lazy migration detects missing indexes on existing collections
via payload_schema. Type mismatch throws IllegalStateException."
```

---

### Task 2: Reactive ingestor — payload indexes + tests

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java`

**Interfaces:**
- Consumes: Same Qdrant gRPC types as Task 1, plus `QdrantFutures.toUni()`, `Uni.join().all().andFailFast()`
- Produces: `ReactiveQdrantEmbeddingIngestor.ensurePayloadIndexes(String, Map<String, PayloadSchemaInfo>)` returning `Uni<Void>` — private, no external consumers

- [ ] **Step 1: Write test — new collection gets all payload indexes**

Add to `ReactiveQdrantEmbeddingIngestorTest.java`:

```java
@Test
void ensureCollectionCreatesPayloadIndexes() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    )).await().indefinitely();

    var info = client.getCollectionInfoAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get();
    var schema = info.getPayloadSchemaMap();

    assertThat(schema).containsKey("content");
    assertThat(schema.get("content").getDataType())
        .isEqualTo(PayloadSchemaType.Text);

    assertThat(schema).containsKey("sourceDocumentId");
    assertThat(schema.get("sourceDocumentId").getDataType())
        .isEqualTo(PayloadSchemaType.Keyword);

    assertThat(schema).containsKey("tenantId");
    assertThat(schema.get("tenantId").getDataType())
        .isEqualTo(PayloadSchemaType.Keyword);
}
```

Add import: `import io.qdrant.client.grpc.Collections.PayloadSchemaType;`

- [ ] **Step 2: Write test — migration adds missing indexes**

```java
@Test
void ensureCollectionAddsIndexesToExistingCollection() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

    var denseParams = io.qdrant.client.grpc.Collections.VectorParams.newBuilder()
        .setSize(DENSE_DIM)
        .setDistance(io.qdrant.client.grpc.Collections.Distance.Cosine)
        .build();
    var paramsMap = io.qdrant.client.grpc.Collections.VectorParamsMap.newBuilder()
        .putMap("dense", denseParams)
        .build();
    client.createCollectionAsync(
        io.qdrant.client.grpc.Collections.CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(io.qdrant.client.grpc.Collections.VectorsConfig.newBuilder()
                .setParamsMap(paramsMap).build())
            .build()).get();

    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    )).await().indefinitely();

    var info = client.getCollectionInfoAsync(collection).get();
    var schema = info.getPayloadSchemaMap();

    assertThat(schema).containsKey("content");
    assertThat(schema.get("content").getDataType()).isEqualTo(PayloadSchemaType.Text);
    assertThat(schema).containsKey("sourceDocumentId");
    assertThat(schema.get("sourceDocumentId").getDataType()).isEqualTo(PayloadSchemaType.Keyword);
    assertThat(schema).containsKey("tenantId");
    assertThat(schema.get("tenantId").getDataType()).isEqualTo(PayloadSchemaType.Keyword);
}
```

- [ ] **Step 3: Write test — idempotent on already-indexed collection**

```java
@Test
void ensureCollectionIdempotentOnAlreadyIndexedCollection() throws Exception {
    CorpusRef corpus = uniqueCorpus();

    store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    )).await().indefinitely();

    ReactiveQdrantEmbeddingIngestor freshStore = new ReactiveQdrantEmbeddingIngestor(
        client,
        new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null,
        TenancyStrategy.SEPARATE_COLLECTIONS,
        "dense", "sparse",
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        Integer.MAX_VALUE,
        DenseQuantization.NONE, true
    );

    freshStore.ingest(corpus, List.of(
        new ChunkInput("more content", "doc-2", Map.of())
    )).await().indefinitely();

    List<String> docs = freshStore.listDocuments(corpus).await().indefinitely();
    assertThat(docs).containsExactlyInAnyOrder("doc-1", "doc-2");
}
```

- [ ] **Step 4: Write test — type mismatch throws IllegalStateException**

```java
@Test
void ensureCollectionThrowsOnIndexTypeMismatch() throws Exception {
    CorpusRef corpus = uniqueCorpus();
    String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

    var denseParams = io.qdrant.client.grpc.Collections.VectorParams.newBuilder()
        .setSize(DENSE_DIM)
        .setDistance(io.qdrant.client.grpc.Collections.Distance.Cosine)
        .build();
    var paramsMap = io.qdrant.client.grpc.Collections.VectorParamsMap.newBuilder()
        .putMap("dense", denseParams)
        .build();
    client.createCollectionAsync(
        io.qdrant.client.grpc.Collections.CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(io.qdrant.client.grpc.Collections.VectorsConfig.newBuilder()
                .setParamsMap(paramsMap).build())
            .build()).get();

    client.createPayloadIndexAsync(collection, "content",
        PayloadSchemaType.Keyword, null, true, null, null).get();

    assertThatThrownBy(() -> store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())
    )).await().indefinitely())
        .hasMessageContaining("content")
        .hasMessageContaining("Text")
        .hasMessageContaining("Keyword");
}
```

- [ ] **Step 5: Run all four new tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="ReactiveQdrantEmbeddingIngestorTest#ensureCollectionCreatesPayloadIndexes+ensureCollectionAddsIndexesToExistingCollection+ensureCollectionIdempotentOnAlreadyIndexedCollection+ensureCollectionThrowsOnIndexTypeMismatch"`

Expected: FAIL — `ensurePayloadIndexes` does not exist yet.

- [ ] **Step 6: Implement `ensurePayloadIndexes` in `ReactiveQdrantEmbeddingIngestor`**

Add imports to `ReactiveQdrantEmbeddingIngestor.java`:

```java
import io.qdrant.client.grpc.Collections.PayloadIndexParams;
import io.qdrant.client.grpc.Collections.PayloadSchemaInfo;
import io.qdrant.client.grpc.Collections.PayloadSchemaType;
import io.qdrant.client.grpc.Collections.TextIndexParams;
import io.qdrant.client.grpc.Collections.TokenizerType;
```

Add private method after `buildCreateRequest`:

```java
private Uni<Void> ensurePayloadIndexes(String collection,
        Map<String, PayloadSchemaInfo> existingSchema) {
    checkIndexType(existingSchema, "content", PayloadSchemaType.Text, collection);
    checkIndexType(existingSchema, "sourceDocumentId", PayloadSchemaType.Keyword, collection);
    checkIndexType(existingSchema, "tenantId", PayloadSchemaType.Keyword, collection);

    List<Uni<Void>> pending = new ArrayList<>();

    if (!existingSchema.containsKey("content")) {
        PayloadIndexParams textParams = PayloadIndexParams.newBuilder()
            .setTextIndexParams(TextIndexParams.newBuilder()
                .setTokenizer(TokenizerType.Word)
                .setLowercase(true)
                .setMinTokenLen(2)
                .setMaxTokenLen(40)
                .build())
            .build();
        pending.add(QdrantFutures.toUni(
            client.createPayloadIndexAsync(collection, "content",
                PayloadSchemaType.Text, textParams, true, null, null))
            .replaceWithVoid());
    }
    if (!existingSchema.containsKey("sourceDocumentId")) {
        pending.add(QdrantFutures.toUni(
            client.createPayloadIndexAsync(collection, "sourceDocumentId",
                PayloadSchemaType.Keyword, null, true, null, null))
            .replaceWithVoid());
    }
    if (!existingSchema.containsKey("tenantId")) {
        pending.add(QdrantFutures.toUni(
            client.createPayloadIndexAsync(collection, "tenantId",
                PayloadSchemaType.Keyword, null, true, null, null))
            .replaceWithVoid());
    }

    if (pending.isEmpty()) return Uni.createFrom().voidItem();
    return Uni.join().all(pending).andFailFast().replaceWithVoid();
}

private static void checkIndexType(Map<String, PayloadSchemaInfo> schema,
        String field, PayloadSchemaType expected, String collection) {
    PayloadSchemaInfo info = schema.get(field);
    if (info != null && info.getDataType() != expected) {
        throw new IllegalStateException(
            "Payload index type mismatch on field '" + field
                + "' in collection '" + collection
                + "': expected " + expected + " but found " + info.getDataType());
    }
}
```

- [ ] **Step 7: Wire `ensurePayloadIndexes` into `ensureCollection`**

In the `ensureCollection` method, modify the existing-collection path. The current code has:

```java
.invoke(info -> {
    int existingDim = (int) info.getConfig().getParams()
        .getVectorsConfig().getParamsMap().getMapMap()
        .get(denseVectorName).getSize();
    if (existingDim != denseDimension) {
        throw new IllegalStateException(...);
    }
})
.replaceWithVoid();
```

Replace with:

```java
.chain(info -> {
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
    return ensurePayloadIndexes(k, info.getPayloadSchemaMap());
});
```

In the new-collection path, change:

```java
return QdrantFutures.toUni(
    client.createCollectionAsync(buildCreateRequest(k)))
    .replaceWithVoid();
```

to:

```java
return QdrantFutures.toUni(
    client.createCollectionAsync(buildCreateRequest(k)))
    .chain(() -> ensurePayloadIndexes(k, Map.of()));
```

- [ ] **Step 8: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveQdrantEmbeddingIngestorTest`

Expected: ALL PASS (existing tests + 4 new tests).

- [ ] **Step 9: Run full rag module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: ALL PASS — no regressions in retriever, bridge, or other tests.

- [ ] **Step 10: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java
git commit -m "feat(#47,#50): payload indexes in reactive QdrantEmbeddingIngestor

Add ensurePayloadIndexes() returning Uni<Void> — concurrent index creation
via Uni.join().all().andFailFast(). Same index set and type validation as
blocking variant. Lazy migration for existing collections."
```
